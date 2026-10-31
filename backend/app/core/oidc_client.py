"""Google authorization-code adapter. No runtime, network or credential at import.

The caller supplies a trusted HTTP transport, TransactionStore and UTC clock.
complete_callback() consumes through the existing manager before token exchange.
The private JOSE helpers are not application entry points. No session/admission.
"""

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
import hmac
import json
import re
from urllib.parse import urlencode

import httpx

from app.core.identity import VerifiedExternalIdentity
from app.core.oidc_config import OidcConfig
from app.core.oidc_transactions import (
    CONTRACT_VERSION, OidcTransaction, TransactionStart, OidcTransactionManager,
    TransactionStore, TransactionCommitUncertain, TransactionStoreUnavailable,
)


ISSUER = "https://accounts.google.com"
AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
JWKS_ENDPOINT = "https://www.googleapis.com/oauth2/v3/certs"
MAX_RESPONSE_BYTES = 65536
MAX_TOKEN_BYTES = 16384
PERSONAL_DOMAINS = frozenset((
    "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com",
    "yahoo.com", "icloud.com", "proton.me", "protonmail.com", "aol.com",
))


class OidcClientRejected(ValueError):
    def __init__(self):
        super().__init__("OIDC_CLIENT_REJECTED")


class OidcClientUnavailable(OidcClientRejected):
    def __init__(self):
        ValueError.__init__(self, "OIDC_CLIENT_UNAVAILABLE")


def _raise(kind):
    try:
        raise kind() from None
    except OidcClientRejected as error:
        error.__context__ = error.__cause__ = None
        error.__suppress_context__ = True
        raise


def _safe(function):
    @wraps(function)
    def checked(*args, **kwargs):
        kind = OidcClientRejected
        try:
            return function(*args, **kwargs)
        except OidcClientUnavailable:
            kind = OidcClientUnavailable
        except Exception:
            pass
        _raise(kind)
    return checked


def _require(value):
    if not value:
        raise OidcClientRejected()


def _text(value, maximum):
    return (type(value) is str and 0 < len(value) <= maximum
            and value.isascii() and all(32 < ord(c) < 127 for c in value))


def _token(value):
    return (_text(value, 43) and len(value) == 43
            and re.fullmatch(r"[A-Za-z0-9_-]{43}", value) is not None
            and base64.urlsafe_b64encode(base64.urlsafe_b64decode(value + "=")).rstrip(b"=").decode() == value)


def _utc(value):
    return type(value) is datetime and value.tzinfo is not None and value.utcoffset() == timedelta(0)


def _domain(value):
    return (_text(value, 253) and value == value.lower() and "." in value
            and all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", x)
                    for x in value.split(".")))


def _unique(pairs):
    result = {}
    for name, value in pairs:
        _require(name not in result)
        result[name] = value
    return result


def _json(raw):
    value = json.loads(raw, object_pairs_hook=_unique,
                       parse_constant=lambda _: _raise(OidcClientRejected))
    _require(type(value) is dict)
    return value


def _jwt_library():
    try:
        import jwt
        import cryptography  # noqa: F401 -- fail closed before any exchange
        return jwt
    except ImportError:
        raise OidcClientUnavailable() from None


class _BorrowedTransport(httpx.BaseTransport):
    """Per-request clients must not close the explicitly caller-owned transport."""

    def __init__(self, transport):
        self._transport = transport

    def handle_request(self, request):
        return self._transport.handle_request(request)


class EmailAssurance(str, Enum):
    GOOGLE_WORKSPACE = "google_workspace"
    INDEPENDENT_VERIFICATION_REQUIRED = "independent_verification_required"


@dataclass(frozen=True, slots=True, repr=False)
class ProfessionalIdentityResult:
    """Signature-verified external key; email assurance is a separate decision.

    A pending result must not be admitted as a verified professional identity.
    Neither outcome grants a company membership or authenticates a local user.
    """
    external_identity: VerifiedExternalIdentity
    email: str
    email_assurance: EmailAssurance

    @property
    def professional_email_verified(self):
        return self.email_assurance is EmailAssurance.GOOGLE_WORKSPACE

    @property
    def access_authorized(self):
        return False

    def __bool__(self):
        _raise(OidcClientRejected)


class GoogleOidcClient:
    """RS256-only Google profile, fixed HTTPS endpoints, no discovery/redirects.

    Explicit approved domains are eligibility configuration, NOT company grants.
    A transport is a trusted server dependency, never request-supplied. HTTPX
    phase timeouts do not promise a total wall-clock deadline against slow peers.
    """

    @_safe
    def __init__(self, *, config: OidcConfig, approved_domains: tuple[str, ...],
                 transport: httpx.BaseTransport, clock, store: TransactionStore,
                 allowed_return_targets: tuple[str, ...]):
        _require(type(config) is OidcConfig)
        self._config = OidcConfig.model_validate(dict(config))
        _require(self._config.issuer == ISSUER and self._config.signature_algorithms == ("RS256",))
        _require(type(approved_domains) is tuple and 0 < len(approved_domains) <= 64
                 and all(type(x) is str for x in approved_domains))
        _require(all(_domain(x) and x not in PERSONAL_DOMAINS for x in approved_domains)
                 and len(set(approved_domains)) == len(approved_domains))
        _require(isinstance(transport, httpx.BaseTransport) and callable(clock))
        self._domains = approved_domains
        self._transport = transport
        self._clock = clock
        self._transactions = OidcTransactionManager(
            config=self._config, store=store, clock=clock,
            allowed_return_targets=allowed_return_targets,
        )

    def _now(self):
        value = self._clock()
        _require(_utc(value))
        return value

    def _transaction(self, tx):
        _require(type(tx) is OidcTransaction and tx.contract_version == CONTRACT_VERSION)
        _require((tx.issuer, tx.client_id, tx.callback_url) ==
                 (ISSUER, self._config.client_id, self._config.callback_url))
        _require(_token(tx.nonce) and _token(tx.code_verifier))
        _require(_utc(tx.created_at) and _utc(tx.expires_at)
                 and tx.created_at <= self._now() < tx.expires_at
                 and (tx.expires_at - tx.created_at).total_seconds() == self._config.transaction_ttl_seconds)

    @_safe
    def authorization_url(self, start: TransactionStart) -> str:
        _require(type(start) is TransactionStart)
        _require(all(_token(x) for x in (start.state, start.nonce, start.code_challenge)))
        now = self._now()
        _require(start.code_challenge_method == "S256" and _utc(start.expires_at)
                 and now < start.expires_at <= now + timedelta(seconds=self._config.transaction_ttl_seconds))
        return AUTHORIZATION_ENDPOINT + "?" + urlencode({
            "response_type": "code", "client_id": self._config.client_id,
            "redirect_uri": self._config.callback_url, "scope": "openid email",
            "state": start.state, "nonce": start.nonce,
            "code_challenge": start.code_challenge, "code_challenge_method": "S256",
        })

    def _request(self, method, endpoint, data=None):
        _require((method, endpoint) in (("POST", TOKEN_ENDPOINT), ("GET", JWKS_ENDPOINT)))
        try:
            # No environment proxies/netrc, cookies, redirects or automatic retry.
            # The injected transport must itself enforce TLS verification/no retries.
            with httpx.Client(transport=_BorrowedTransport(self._transport), trust_env=False, follow_redirects=False,
                              timeout=httpx.Timeout(5.0, connect=3.0),
                              limits=httpx.Limits(max_connections=1)) as client:
                with client.stream(method, endpoint, data=data, headers={"Accept": "application/json", "Accept-Encoding": "identity"}) as response:
                    _require(response.status_code == 200)
                    _require(response.headers.get("content-type", "").split(";", 1)[0].strip().lower() == "application/json")
                    _require(response.headers.get("content-encoding", "identity") == "identity")
                    chunks = bytearray()
                    for chunk in response.iter_raw():
                        _require(len(chunks) + len(chunk) <= MAX_RESPONSE_BYTES)
                        chunks.extend(chunk)
                    return _json(bytes(chunks))
        except (httpx.HTTPError, OSError):
            raise OidcClientUnavailable() from None

    @_safe
    def complete_callback(self, *, state: str, browser_binding: str, code: str,
                          client_secret: str) -> ProfessionalIdentityResult:
        """Only public identity-producing entry point; no caller-supplied receipt.

        CONFIRMED is the trusted store's promise of a durable commit, checked by
        the existing manager. Python cannot authenticate the adapter's honesty.
        Any failure is terminal for this invocation; no retry/restore is provided.
        """
        _require(_token(state) and _token(browser_binding))
        _require(_text(code, 4096) and _text(client_secret, 4096))
        _jwt_library()  # missing JOSE must not consume the transaction
        try:
            transaction = self._transactions.consume(state=state, browser_binding=browser_binding)
        except (TransactionCommitUncertain, TransactionStoreUnavailable):
            raise OidcClientUnavailable() from None
        return self._exchange(code=code, transaction=transaction, client_secret=client_secret)

    @_safe
    def _exchange(self, *, code: str, transaction: OidcTransaction,
                 client_secret: str) -> ProfessionalIdentityResult:
        """Backend-only; caller must consume state/binding before invoking once.

        No retry after a token request, including a timeout or uncertain response.
        Access/refresh tokens are discarded, never returned to the caller.
        """
        _jwt_library()
        self._transaction(transaction)
        _require(_text(code, 4096) and _text(client_secret, 4096))
        payload = self._request("POST", TOKEN_ENDPOINT, {
            "grant_type": "authorization_code", "code": code,
            "client_id": self._config.client_id, "client_secret": client_secret,
            "redirect_uri": self._config.callback_url, "code_verifier": transaction.code_verifier,
        })
        _require("error" not in payload and "id_token" in payload)
        return self._verify_id_token(id_token=payload["id_token"], transaction=transaction)

    @_safe
    def _verify_id_token(self, *, id_token: str, transaction: OidcTransaction) -> ProfessionalIdentityResult:
        library = _jwt_library()
        self._transaction(transaction)
        _require(_text(id_token, MAX_TOKEN_BYTES))
        parts = id_token.split(".")
        _require(len(parts) == 3 and all(re.fullmatch(r"[A-Za-z0-9_-]+", x) for x in parts))
        def segment(value):
            return _json(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))
        header = segment(parts[0])
        # Never follow jku/x5u or accept an embedded key/critical extension.
        _require(set(header) <= {"alg", "kid", "typ"} and header.get("alg") == "RS256"
                 and _text(header.get("kid"), 256) and header.get("typ", "JWT") == "JWT")
        encoded_claims = segment(parts[1])  # reject duplicate JSON names before JOSE
        jwks = self._request("GET", JWKS_ENDPOINT)
        keys = jwks.get("keys")
        _require(type(keys) is list and 0 < len(keys) <= 32 and all(type(k) is dict for k in keys))
        _require(all(_text(k.get("kid"), 256) for k in keys)
                 and len({k["kid"] for k in keys}) == len(keys))
        matches = [k for k in keys if k["kid"] == header["kid"]]
        _require(len(matches) == 1)
        key = matches[0]
        _require(key.get("kty") == "RSA" and key.get("alg", "RS256") == "RS256"
                 and key.get("use", "sig") == "sig" and key.get("key_ops", ["verify"]) == ["verify"]
                 and not any(k in key for k in ("d", "p", "q", "dp", "dq", "qi", "oth")))
        _require(_text(key.get("n"), 2048) and _text(key.get("e"), 16))
        public_key = library.PyJWK.from_dict(key, algorithm="RS256").key
        _require(2048 <= public_key.key_size <= 8192)
        claims = library.decode(id_token, public_key, algorithms=["RS256"],
                                issuer=(ISSUER, "accounts.google.com"), audience=self._config.client_id,
                                options={"require": ["iss", "sub", "aud", "exp", "iat", "nonce", "email", "email_verified"],
                                         "verify_signature": True, "verify_exp": False,
                                         "verify_iat": False, "verify_nbf": False})
        _require(claims == encoded_claims)
        return self._claims(claims, transaction)

    def _claims(self, claims, tx):
        # Signature is library-verified; UTC clock injection controls strict time
        # checks here instead of mixing library wall time with the injected clock.
        _require(claims.get("iss") in (ISSUER, "accounts.google.com"))
        subject = claims.get("sub")
        _require(_text(subject, 255))
        aud = claims.get("aud")
        _require((type(aud) is str and aud == self._config.client_id)
                 or (type(aud) is list and bool(aud) and all(_text(x, 512) for x in aud)
                     and len(set(aud)) == len(aud) and self._config.client_id in aud))
        if "azp" in claims or (type(aud) is list and len(aud) > 1):
            _require(type(claims.get("azp")) is str and claims["azp"] == self._config.client_id)
        now = self._now().timestamp()
        skew = self._config.clock_skew_seconds
        exp, iat = claims.get("exp"), claims.get("iat")
        _require(type(exp) is int and type(iat) is int and 0 <= iat < exp
                 and now < exp + skew and iat <= now + skew
                 and now - iat < self._config.max_id_token_age_seconds + skew
                 and iat >= tx.created_at.timestamp() - skew)
        for name in ("nbf", "auth_time"):
            if name in claims:
                v = claims[name]
                _require(type(v) is int and 0 <= v <= now + skew and v < exp)
                if name == "auth_time":
                    _require(v <= iat + skew)
        _require(_token(claims.get("nonce")) and hmac.compare_digest(claims["nonce"], tx.nonce))
        email = claims.get("email")
        _require(_text(email, 254) and claims.get("email_verified") is True and email.count("@") == 1)
        local, domain = email.rsplit("@", 1)
        _require(re.fullmatch(r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*", local) is not None)
        domain = domain.lower()
        _require(_domain(domain) and domain in self._domains and domain not in PERSONAL_DOMAINS)
        if "hd" in claims:
            _require(type(claims["hd"]) is str and _domain(claims["hd"])
                     and claims["hd"] == domain and claims["hd"] in self._domains)
            assurance = EmailAssurance.GOOGLE_WORKSPACE
        else:
            assurance = EmailAssurance.INDEPENDENT_VERIFICATION_REQUIRED
        # Google documents these two issuer spellings. Canonicalize only this
        # explicit provider alias; email is never used as an identity key.
        return ProfessionalIdentityResult(VerifiedExternalIdentity(ISSUER, subject), email, assurance)
