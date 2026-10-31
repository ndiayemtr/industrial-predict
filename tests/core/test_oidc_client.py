"""Offline only. JOSE doubles are explicitly separated from real RSA tests."""

import base64
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sys
import traceback
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.core import oidc_client as m
from app.core.oidc_config import OidcConfig
from app.core.oidc_transactions import (
    OidcTransaction, TransactionStart, pkce_s256, ConsumptionReceipt, ConsumeStatus,
    InsertStatus, TransactionCommitUncertain,
)


NOW = datetime(2026, 10, 31, 15, tzinfo=timezone.utc)
NONCE = base64.urlsafe_b64encode(b'n' * 32).rstrip(b'=').decode()
VERIFIER = base64.urlsafe_b64encode(b'v' * 32).rstrip(b'=').decode()
STATE = base64.urlsafe_b64encode(b's' * 32).rstrip(b'=').decode()
MARKER = "SYNTHETIC-SENSITIVE-MARKER"


def config(**changes):
    values = dict(issuer=m.ISSUER, client_id="synthetic-client", callback_url="https://app.example.invalid/auth/callback",
                  signature_algorithms=("RS256",), deployment_mode="production",
                  transaction_ttl_seconds=300, clock_skew_seconds=0, max_id_token_age_seconds=300)
    return OidcConfig(**(values | changes))


def transaction():
    return OidcTransaction('a' * 64, 'b' * 64, 'c' * 64, NONCE, VERIFIER, m.ISSUER,
                           config().client_id, config().callback_url, 'd' * 64,
                           "dashboard", NOW - timedelta(seconds=10), NOW + timedelta(seconds=290))


def claims(**changes):
    return dict(iss=m.ISSUER, sub="stable-subject", aud=config().client_id,
                exp=int(NOW.timestamp()) + 120, iat=int(NOW.timestamp()),
                nonce=NONCE, email="Person@factory.example", email_verified=True,
                hd="factory.example") | changes


def encode_json(value):
    return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b'=').decode()


def token(payload=None, header=None):
    return encode_json(header or dict(alg="RS256", kid="test-key")) + '.' + encode_json(payload or claims()) + '.c2ln'


def response(value, status=200, headers=None):
    return httpx.Response(status, headers=headers or {"content-type": "application/json"},
                          stream=httpx.ByteStream(json.dumps(value).encode()))


def keyset():
    return {"keys": [dict(kid="test-key", kty="RSA", alg="RS256", use="sig", n="synthetic", e="AQAB")]}


class StoreDouble:
    """Injected test adapter; not a durable store or locking emulator."""
    def __init__(self, events=None, mode='confirmed'):
        self.record = None
        self.events = events if events is not None else []
        self.mode = mode
        self.calls = 0

    def insert_new(self, tx):
        self.record = tx
        return InsertStatus.CONFIRMED

    def consume(self, condition):
        self.calls += 1
        self.events.append('consume')
        if self.mode == 'uncertain_exception': raise TransactionCommitUncertain()
        if self.mode == 'uncertain': return ConsumptionReceipt(ConsumeStatus.UNCERTAIN)
        if self.mode == 'boolean': return True
        if self.mode == 'absent' or self.record is None: return ConsumptionReceipt(ConsumeStatus.REJECTED)
        tx = self.record
        if self.mode == 'rejected': return ConsumptionReceipt(ConsumeStatus.REJECTED)
        if (condition.state_digest != tx.state_digest or condition.browser_binding_digest != tx.browser_binding_digest
                or not tx.created_at <= condition.now < tx.expires_at):
            return ConsumptionReceipt(ConsumeStatus.REJECTED)
        if self.mode == 'malformed': return ConsumptionReceipt(ConsumeStatus.CONFIRMED, replace(tx, transaction_id='a'*64))
        self.record = None
        self.events.append('commit_acknowledged')
        return ConsumptionReceipt(ConsumeStatus.CONFIRMED, tx)


def client(handler=None, **kwargs):
    return m.GoogleOidcClient(config=kwargs.pop('config', config()), approved_domains=kwargs.pop('approved_domains', ("factory.example",)),
                              transport=httpx.MockTransport(handler or (lambda request: response(keyset()))),
                              clock=kwargs.pop('clock', lambda: NOW),
                              store=kwargs.pop('store', StoreDouble()),
                              allowed_return_targets=('dashboard',), **kwargs)


@pytest.fixture
def jose_double(monkeypatch):
    """No cryptographic guarantee: only exercise adapter/claim policy orchestration."""
    calls = []
    def decode(raw, public_key, **options):
        calls.append(options)
        return json.loads(base64.urlsafe_b64decode(raw.split('.')[1] + '=='))
    library = SimpleNamespace(PyJWK=SimpleNamespace(from_dict=lambda *a, **k: SimpleNamespace(key=SimpleNamespace(key_size=2048))), decode=decode)
    monkeypatch.setattr(m, '_jwt_library', lambda: library)
    return calls


def assert_clean(error):
    assert str(error) in ('OIDC_CLIENT_REJECTED', 'OIDC_CLIENT_UNAVAILABLE')
    assert error.__context__ is None and error.__cause__ is None
    assert error.__suppress_context__ is True
    assert MARKER not in repr(error)
    assert MARKER not in ''.join(traceback.format_exception(error))


def test_authorization_request_uses_existing_pkce_state_nonce():
    start = TransactionStart('a'*64, STATE, NONCE, STATE, pkce_s256(VERIFIER), NOW + timedelta(seconds=100))
    url = client().authorization_url(start)
    assert url.startswith(m.AUTHORIZATION_ENDPOINT + '?')
    query = parse_qs(urlsplit(url).query)
    assert query['scope'] == ['openid email']
    assert query['state'] == [STATE] and query['nonce'] == [NONCE]
    assert query['code_challenge'] == [pkce_s256(VERIFIER)]
    assert 'hd' not in query and 'client_secret' not in query and 'code_verifier' not in query


@pytest.mark.parametrize('changes', [dict(state='bad'), dict(nonce='bad'), dict(code_challenge_method='plain'),
                                  dict(expires_at=NOW), dict(expires_at=NOW + timedelta(seconds=301))])
def test_bad_authorization_start(changes):
    start = TransactionStart('a'*64, STATE, NONCE, STATE, pkce_s256(VERIFIER), NOW + timedelta(seconds=100))
    with pytest.raises(m.OidcClientRejected): client().authorization_url(replace(start, **changes))


@pytest.mark.parametrize('domains', [(), ['factory.example'], ('gmail.com',), ('Factory.example',),
                                    ('factory.example', 'factory.example'), ('factory.example/path',), (object(),)])
def test_closed_eligibility_configuration(domains):
    with pytest.raises(m.OidcClientRejected): client(approved_domains=domains)


@pytest.mark.parametrize('cfg', [config(issuer='https://evil.example'), config(signature_algorithms=('ES256',))])
def test_google_profile_is_fixed(cfg):
    with pytest.raises(m.OidcClientRejected): client(config=cfg)


def test_simulated_workspace_result_has_no_access_and_is_immutable(jose_double):
    result = client()._verify_id_token(id_token=token(), transaction=transaction())
    assert result.external_identity.issuer == m.ISSUER
    assert result.external_identity.subject == 'stable-subject'
    assert result.professional_email_verified is True
    assert result.access_authorized is False
    assert result.email not in repr(result)
    with pytest.raises(FrozenInstanceError): result.email = 'other'
    with pytest.raises(m.OidcClientRejected): bool(result)
    assert jose_double[0]['algorithms'] == ['RS256']
    assert jose_double[0]['options']['verify_signature'] is True


def test_third_party_is_pending_never_simulated_as_verified(jose_double):
    payload = claims(); payload.pop('hd')
    result = client()._verify_id_token(id_token=token(payload), transaction=transaction())
    assert result.email_assurance is m.EmailAssurance.INDEPENDENT_VERIFICATION_REQUIRED
    assert result.professional_email_verified is False and result.access_authorized is False


@pytest.mark.parametrize('change', [
    dict(iss='https://evil.example'), dict(sub=''), dict(aud='other'), dict(aud=['synthetic-client','other']),
    dict(azp='other'), dict(nonce=STATE), dict(exp=int(NOW.timestamp())), dict(iat=int(NOW.timestamp())+1),
    dict(iat=int(NOW.timestamp())-400), dict(exp=True), dict(nbf=int(NOW.timestamp())+1),
    dict(auth_time=int(NOW.timestamp())+1), dict(email_verified=False), dict(email_verified='true'),
    dict(email='person@gmail.com'), dict(email='person@unapproved.example'), dict(hd='other.example'),
    dict(hd=''), dict(email='person@@factory.example'), dict(email='a..b@factory.example'),
    dict(aud=[]), dict(aud=['synthetic-client',True]), dict(nbf=False),
])
def test_claim_policy_refusals_with_explicit_jose_double(jose_double, change):
    with pytest.raises(m.OidcClientRejected): client()._verify_id_token(id_token=token(claims(**change)), transaction=transaction())


@pytest.mark.parametrize('name', ['iss','sub','aud','exp','iat','nonce','email','email_verified'])
def test_missing_required_claims_with_double(jose_double, name):
    payload=claims(); payload.pop(name)
    with pytest.raises(m.OidcClientRejected): client()._verify_id_token(id_token=token(payload), transaction=transaction())


@pytest.mark.parametrize('header', [dict(alg='none',kid='test-key'), dict(alg='HS256',kid='test-key'),
                                    dict(alg='RS256',kid='unknown'), dict(alg='RS256'),
                                    dict(alg='RS256',kid='test-key',jku='https://evil.example'),
                                    dict(alg='RS256',kid='test-key',crit=['custom'])])
def test_header_and_unknown_key_fail_closed(jose_double, header):
    with pytest.raises(m.OidcClientRejected): client()._verify_id_token(id_token=token(header=header), transaction=transaction())


@pytest.mark.parametrize('keys', [[], [dict(kid='test-key', kty='oct', n='x', e='AQAB')],
                                keyset()['keys']*2, [dict(kid='test-key',kty='RSA',n='x',e='AQAB',d='private')]])
def test_jwks_refusals(jose_double, keys):
    with pytest.raises(m.OidcClientRejected):
        client(lambda r: response({'keys':keys}))._verify_id_token(id_token=token(), transaction=transaction())


def test_exchange_fixed_endpoint_pkce_timeouts_and_token_discard(jose_double):
    calls=[]
    def handler(request):
        calls.append(request)
        assert request.url.scheme == 'https'
        assert request.headers['accept-encoding'] == 'identity'
        if request.method=='POST': return response(dict(id_token=token(), access_token=MARKER, refresh_token=MARKER))
        return response(keyset())
    result=client(handler)._exchange(code='synthetic-code', client_secret='synthetic-client-secret', transaction=transaction())
    assert [str(r.url) for r in calls] == [m.TOKEN_ENDPOINT,m.JWKS_ENDPOINT]
    fields=parse_qs(calls[0].content.decode())
    assert fields['code_verifier']==[VERIFIER] and fields['grant_type']==['authorization_code']
    assert calls[0].extensions['timeout']==dict(connect=3.0,read=5.0,write=5.0,pool=5.0)
    assert not hasattr(result,'access_token') and not hasattr(result,'refresh_token')


@pytest.mark.parametrize('kind', ['timeout','redirect','provider','oversize','encoding','mime','duplicate'])
def test_network_and_provider_refusals(jose_double, kind):
    calls=[]
    def handler(r):
        calls.append(r)
        if kind=='timeout': raise httpx.ReadTimeout(MARKER)
        if kind=='redirect': return response({},302,{'location':'https://evil.example'})
        if kind=='provider': return response({'error':MARKER})
        if kind=='oversize': return httpx.Response(200,headers={'content-type':'application/json'},stream=httpx.ByteStream(b' '*65537))
        if kind=='encoding': return response({},headers={'content-type':'application/json','content-encoding':'custom'})
        if kind=='mime': return response({},headers={'content-type':'text/html'})
        return httpx.Response(200,headers={'content-type':'application/json'},stream=httpx.ByteStream(b'{"id_token":"x","id_token":"y"}'))
    try:
        raise RuntimeError(MARKER)
    except RuntimeError:
        with pytest.raises(m.OidcClientRejected) as caught:
            client(handler)._exchange(code='synthetic',client_secret='synthetic',transaction=transaction())
    assert_clean(caught.value)
    assert len(calls)==1  # no redirect, refresh or automatic retry


def test_clock_error_is_sanitized_even_in_caller_handler():
    def clock(): raise RuntimeError(MARKER)
    try:
        raise RuntimeError(MARKER)
    except RuntimeError:
        with pytest.raises(m.OidcClientRejected) as caught:
            start=TransactionStart('a'*64,STATE,NONCE,STATE,pkce_s256(VERIFIER),NOW+timedelta(seconds=100))
            client(clock=clock).authorization_url(start)
    assert_clean(caught.value)


@pytest.mark.parametrize('change', [dict(issuer='https://evil.example'),dict(client_id='other'),dict(callback_url='https://evil.example'),
                                  dict(expires_at=NOW),dict(code_verifier='bad'),dict(contract_version='other')])
def test_invalid_transaction_never_calls_transport(jose_double, change):
    def handler(r): pytest.fail('unexpected HTTP call')
    with pytest.raises(m.OidcClientRejected):
        client(handler)._exchange(code='synthetic',client_secret='synthetic',transaction=replace(transaction(),**change))


def test_missing_jose_dependency_fails_before_http():
    if importlib.util.find_spec('jwt') and importlib.util.find_spec('cryptography'):
        pytest.skip('dependency availability test applies only to missing JOSE environment')
    with pytest.raises(m.OidcClientUnavailable) as caught:
        client(lambda r: pytest.fail('HTTP before JOSE availability'))._exchange(code='synthetic',client_secret='synthetic',transaction=transaction())
    assert_clean(caught.value)


def test_multi_audience_azp_and_google_alias_with_double(jose_double):
    payload=claims(aud=['synthetic-client','other'],azp='synthetic-client',iss='accounts.google.com')
    result=client()._verify_id_token(id_token=token(payload),transaction=transaction())
    assert result.external_identity.issuer==m.ISSUER
    assert result.access_authorized is False


def test_duplicate_token_json_and_oversize_fail_before_http(jose_double):
    def handler(r): pytest.fail('HTTP before input validation')
    duplicate=encode_json(dict(alg='RS256',kid='test-key'))+'.'+base64.urlsafe_b64encode(b'{"iss":"x","iss":"y"}').rstrip(b'=').decode()+'.c2ln'
    for raw in (duplicate,'x'*16385,'not-a-jwt'):
        with pytest.raises(m.OidcClientRejected): client(handler)._verify_id_token(id_token=raw,transaction=transaction())


def test_jose_exception_is_sanitized(jose_double, monkeypatch):
    def failed(*a,**k): raise RuntimeError(MARKER)
    monkeypatch.setattr(m,'_jwt_library',failed)
    try:
        raise RuntimeError(MARKER)
    except RuntimeError:
        with pytest.raises(m.OidcClientRejected) as caught:
            client()._verify_id_token(id_token=token(),transaction=transaction())
    assert_clean(caught.value)


def test_import_does_not_create_http_client(monkeypatch):
    import importlib
    def failed(*a,**k): pytest.fail('HTTP resource created at import')
    monkeypatch.setattr(httpx,'Client',failed)
    importlib.reload(m)


@pytest.fixture
def rsa_material():
    jwt=pytest.importorskip('jwt', reason='PyJWT absent: real RSA verification not executable')
    pytest.importorskip('cryptography', reason='cryptography absent: real RSA verification not executable')
    from cryptography.hazmat.primitives.asymmetric import rsa
    private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    key=json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key())) | dict(kid='test-key',alg='RS256',use='sig')
    return jwt,private,key


@pytest.mark.parametrize('case', ['valid','bad_signature','issuer','audience','nonce','expired','algorithm','unknown_key','missing_claim'])
def test_real_pyjwt_rsa_validation(rsa_material, case):
    jwt,private,key=rsa_material
    payload=claims(); headers=dict(kid='test-key')
    if case=='issuer': payload['iss']='https://evil.example'
    if case=='audience': payload['aud']='other'
    if case=='nonce': payload['nonce']=STATE
    if case=='expired': payload['exp']=int(NOW.timestamp())
    if case=='unknown_key': headers['kid']='unknown'
    if case=='missing_claim': payload.pop('sub')
    raw=jwt.encode(payload,private,algorithm='RS256',headers=headers)
    if case=='bad_signature':
        a,b,s=raw.split('.'); raw=a+'.'+b+'.'+('A' if s[0]!='A' else 'B')+s[1:]
    if case=='algorithm': raw=jwt.encode(payload,'synthetic-test-hmac-key-of-sufficient-length',algorithm='HS256',headers=headers)
    c=client(lambda r: response({'keys':[key]}))
    if case=='valid': assert c._verify_id_token(id_token=raw,transaction=transaction()).professional_email_verified
    else:
        with pytest.raises(m.OidcClientRejected): c._verify_id_token(id_token=raw,transaction=transaction())


def test_public_callback_consumes_before_exchange_and_has_no_raw_identity_entry(jose_double):
    events=[]
    store=StoreDouble(events)
    start=None
    def handler(request):
        assert events[:2]==['consume','commit_acknowledged']
        assert request.headers['accept-encoding']=='identity'
        events.append(request.method)
        if request.method=='POST': return response({'id_token':token(claims(nonce=start.nonce))})
        return response(keyset())
    c=client(handler,store=store)
    start=c._transactions.create(return_target='dashboard')
    result=c.complete_callback(state=start.state,browser_binding=start.browser_binding,
                               code='synthetic',client_secret='synthetic')
    assert result.external_identity.subject=='stable-subject'
    assert result.access_authorized is False
    assert events==['consume','commit_acknowledged','POST','GET']
    assert not hasattr(c,'exchange') and not hasattr(c,'verify_id_token')
    assert store.record is None


@pytest.mark.parametrize('mode', ['absent','rejected','uncertain','uncertain_exception','boolean','malformed'])
def test_callback_unconfirmed_consumption_never_calls_network(jose_double, mode):
    store=StoreDouble(mode=mode)
    c=client(lambda r: pytest.fail('network without confirmed consumption'),store=store)
    start=c._transactions.create(return_target='dashboard')
    with pytest.raises(m.OidcClientRejected) as caught:
        c.complete_callback(state=start.state,browser_binding=start.browser_binding,
                            code='synthetic',client_secret='synthetic')
    assert_clean(caught.value)
    assert store.calls==1


@pytest.mark.parametrize('case', ['malformed_state','malformed_binding','wrong_state','wrong_binding','expired'])
def test_callback_correlation_and_expiry_refusals(jose_double, case):
    store=StoreDouble()
    c=client(lambda r: pytest.fail('network for invalid callback'),store=store)
    start=c._transactions.create(return_target='dashboard')
    state,binding=start.state,start.browser_binding
    if case=='malformed_state': state='invalid'
    if case=='malformed_binding': binding='invalid'
    if case=='wrong_state': state=STATE
    if case=='wrong_binding': binding=STATE
    if case=='expired':
        store.record=replace(store.record,created_at=NOW-timedelta(seconds=300),expires_at=NOW)
    with pytest.raises(m.OidcClientRejected):
        c.complete_callback(state=state,browser_binding=binding,code='synthetic',client_secret='synthetic')
    assert store.calls==(0 if case.startswith('malformed') else 1)


def test_callback_replay_is_rejected_without_second_exchange(jose_double):
    calls=[]; store=StoreDouble(); start=None
    def handler(r):
        calls.append(r)
        return response({'id_token':token(claims(nonce=start.nonce))}) if r.method=='POST' else response(keyset())
    c=client(handler,store=store)
    start=c._transactions.create(return_target='dashboard')
    inputs=dict(state=start.state,browser_binding=start.browser_binding,code='synthetic',client_secret='synthetic')
    assert c.complete_callback(**inputs).access_authorized is False
    with pytest.raises(m.OidcClientRejected): c.complete_callback(**inputs)
    assert len(calls)==2 and store.calls==2


@pytest.mark.parametrize('stage', ['token','jwks'])
def test_public_callback_rejects_compression_on_both_endpoints(jose_double, stage):
    store=StoreDouble(); start=None; calls=[]
    def handler(r):
        calls.append(r)
        assert r.headers['accept-encoding']=='identity'
        value={'id_token':token(claims(nonce=start.nonce))} if r.method=='POST' else keyset()
        compressed=(stage=='token' and r.method=='POST') or (stage=='jwks' and r.method=='GET')
        return response(value,headers={'content-type':'application/json',**({'content-encoding':'gzip'} if compressed else {})})
    c=client(handler,store=store)
    start=c._transactions.create(return_target='dashboard')
    with pytest.raises(m.OidcClientRejected):
        c.complete_callback(state=start.state,browser_binding=start.browser_binding,code='synthetic',client_secret='synthetic')
    assert len(calls)==(1 if stage=='token' else 2)
    assert store.record is None  # no restoration after provider failure


def test_real_decode_signature_exception_is_sanitized_in_public_callback(rsa_material,monkeypatch):
    jwt,private,key=rsa_material
    store=StoreDouble(); start=None; decode_errors=[]
    original_decode=jwt.decode
    def observed_decode(*args,**kwargs):
        try:
            return original_decode(*args,**kwargs)
        except jwt.InvalidSignatureError:
            decode_errors.append('real_invalid_signature')
            raise
    monkeypatch.setattr(jwt,'decode',observed_decode)
    def handler(r):
        if r.method=='GET': return response({'keys':[key]})
        raw=jwt.encode(claims(nonce=start.nonce),private,algorithm='RS256',headers={'kid':'test-key'})
        a,b,s=raw.split('.'); raw=a+'.'+b+'.'+('A' if s[0]!='A' else 'B')+s[1:]
        return response({'id_token':raw})
    c=client(handler,store=store)
    start=c._transactions.create(return_target='dashboard')
    try:
        raise RuntimeError(MARKER)
    except RuntimeError:
        with pytest.raises(m.OidcClientRejected) as caught:
            c.complete_callback(state=start.state,browser_binding=start.browser_binding,code='synthetic',client_secret='synthetic')
    assert decode_errors==['real_invalid_signature']
    assert_clean(caught.value)
    assert store.record is None


def test_real_rsa_through_public_callback(rsa_material):
    jwt,private,key=rsa_material
    store=StoreDouble(); start=None
    def handler(r):
        if r.method=='GET': return response({'keys':[key]})
        return response({'id_token':jwt.encode(claims(nonce=start.nonce),private,algorithm='RS256',headers={'kid':'test-key'})})
    c=client(handler,store=store)
    start=c._transactions.create(return_target='dashboard')
    result=c.complete_callback(state=start.state,browser_binding=start.browser_binding,code='synthetic',client_secret='synthetic')
    assert result.professional_email_verified is True and result.access_authorized is False
