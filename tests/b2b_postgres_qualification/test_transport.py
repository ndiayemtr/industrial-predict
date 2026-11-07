"""Offline only: scripted PostgreSQL bytes and in-memory TLS, never a TCP server."""

import base64
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import ssl
import struct
import traceback

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from b2b_postgres_qualification import collectors as c, transport as t, evidence as e
from b2b_postgres_qualification.contracts import Rejected, ExecutionDisabled
from b2b_postgres_qualification.test_contracts import campaign as base_campaign


PRIVATE = 'SYNTHETIC-SECRET-DO-NOT-LOG'


@pytest.fixture(autouse=True)
def no_external_io(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('External I/O forbidden')
    for name in ('socket.socket.connect', 'socket.socket.connect_ex', 'socket.create_connection',
                 'socket.getaddrinfo', 'subprocess.run', 'subprocess.Popen', 'os.system'):
        monkeypatch.setattr(name, forbidden)


@pytest.fixture
def tls_material(base_campaign, tmp_path):
    now = datetime.now(timezone.utc)
    root_key, key = ec.generate_private_key(ec.SECP256R1()), ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Ephemeral offline CA')])
    root = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
        .public_key(root_key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(root_key.public_key()), critical=False)
        .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
        .sign(root_key, hashes.SHA256()))
    leaf = (x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, base_campaign.host)]))
        .issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(base_campaign.host)]), critical=False)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(root_key.public_key()), critical=False)
        .sign(root_key, hashes.SHA256()))
    cert_file, key_file = tmp_path / 'server.pem', tmp_path / 'server-key.pem'
    cert_file.write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.load_cert_chain(cert_file, key_file)
    # Private key files are fixture-local, deleted immediately after OpenSSL loads them.
    key_file.unlink()
    cert_file.unlink()
    return root.public_bytes(serialization.Encoding.DER), leaf.public_bytes(serialization.Encoding.DER), server


@pytest.fixture
def campaign(base_campaign, tls_material):
    return replace(base_campaign, ca_sha256=hashlib.sha256(tls_material[0]).hexdigest())


@pytest.fixture
def policy(tls_material):
    return e.CollectorPolicy('offline', '1' * 64, '2' * 64,
        datetime.now(timezone.utc), tls_material[0])


def memory_handshake(context, server_context, hostname):
    ci, co, si, so = (ssl.MemoryBIO() for _ in range(4))
    client = context.wrap_bio(ci, co, server_hostname=hostname)
    server = server_context.wrap_bio(si, so, server_side=True)
    done = [False, False]
    for _ in range(20):
        for index, peer in enumerate((client, server)):
            if not done[index]:
                try:
                    peer.do_handshake()
                    done[index] = True
                except ssl.SSLWantReadError:
                    pass
        if co.pending:
            si.write(co.read())
        if so.pending:
            ci.write(so.read())
        if all(done):
            return client
    raise AssertionError('Handshake did not finish')


def test_real_openssl_memory_handshake_and_peer_capture(campaign, tls_material):
    context = t._context(tls_material[0])
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
    assert context.minimum_version == ssl.TLSVersion.TLSv1_2
    assert not context.hostname_checks_common_name
    peer = memory_handshake(context, tls_material[2], campaign.host)
    assert peer.getpeercert(binary_form=True) == tls_material[1]


def test_real_openssl_rejects_wrong_hostname(tls_material):
    with pytest.raises(ssl.SSLCertVerificationError):
        memory_handshake(t._context(tls_material[0]), tls_material[2], 'wrong.invalid')


def test_real_openssl_rejects_untrusted_chain(tls_material):
    # No default trust roots: server CA is absent from this context.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    with pytest.raises(ssl.SSLCertVerificationError):
        # Correct SAN, wrong trust: distinguish this failure from hostname failure.
        hostname = x509.load_der_x509_certificate(tls_material[1]).extensions.get_extension_for_class(
            x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName)[0]
        memory_handshake(context, tls_material[2], hostname)


def packet(kind, body):
    return kind + struct.pack('!I', len(body) + 4) + body


def result(rows):
    if not rows:
        return packet(b'C', b'ROLLBACK\0') + packet(b'Z', b'I')
    columns = [(name, 16 if type(value) is bool else 23 if type(value) is int else 25)
               for name, value in rows[0].items()]
    desc = struct.pack('!H', len(columns))
    for name, oid in columns:
        desc += name.encode() + b'\0' + struct.pack('!IhIhih', 0, 0, oid, -1, -1, 0)
    output = packet(b'T', desc)
    for row in rows:
        body = struct.pack('!H', len(columns))
        for name, oid in columns:
            value = row[name]
            if value is None:
                body += struct.pack('!i', -1)
            else:
                raw = (('t' if value else 'f') if oid == 16 else str(value)).encode()
                body += struct.pack('!I', len(raw)) + raw
        output += packet(b'D', body)
    return output + packet(b'C', b'SELECT 1\0') + packet(b'Z', b'I')


class ScriptedSocket:
    """Fake wire server; TLS methods are claims, not live TLS evidence."""

    def __init__(self, campaign, certificate):
        self.campaign, self.certificate = campaign, certificate
        self.input, self.sent, self.closed = b'', [], 0
        self.identity = dict(database=campaign.database, session_role=campaign.roles[2], role=campaign.roles[2],
            address=campaign.server_address, port=5432, version='170010', cluster=campaign.cluster_name,
            instance=campaign.instance_id, dev_marker=None, read_only='on', default_read_only='on',
            pid=103, elevated=False)
        self.ssl_reply, self.auth = b'S', 10
        self.bad_signature, self.handshake_error = False, None
        self.query_results = {}

    def settimeout(self, timeout):
        assert 0 < timeout <= 3

    def connect(self, address):
        assert address == (self.campaign.server_address, 5432)

    def getpeername(self):
        return self.campaign.server_address, 5432

    def do_handshake(self):
        if self.handshake_error:
            raise self.handshake_error

    def version(self): return 'TLSv1.3'
    def fileno(self): return -1 if self.closed else 42
    def getpeercert(self, *, binary_form): return self.certificate
    def close(self): self.closed += 1

    def recv(self, count):
        # Force partial reads, including headers.
        value, self.input = self.input[:min(count, 7)], self.input[min(count, 7):]
        return value

    def sendall(self, data):
        self.sent.append(data)
        if data == struct.pack('!II', 8, 80877103):
            self.input += self.ssl_reply
        elif data[:1] == b'Q':
            query = data[5:-1].decode()
            self.input += self.query_results.get(query, result([self.identity]) if query == c.IDENTITY_SQL else result([]))
        elif data[:1] == b'p':
            body = data[5:]
            if body.startswith(b'SCRAM-SHA-256\0'):
                self.first = body.split(b'\0', 1)[1][4:][3:]
                nonce = self.first.split(b'r=', 1)[1] + b'server-extension'
                self.server_first = b'r=' + nonce + b',s=' + base64.b64encode(b'offline-salt') + b',i=4096'
                self.input += packet(b'R', struct.pack('!I', 11) + self.server_first)
            else:
                final, proof = body.rsplit(b',p=', 1)
                auth = self.first + b',' + self.server_first + b',' + final
                salted = hashlib.pbkdf2_hmac('sha256', PRIVATE.encode(), b'offline-salt', 4096)
                client_key = hmac.digest(salted, b'Client Key', 'sha256')
                signature = hmac.digest(hashlib.sha256(client_key).digest(), auth, 'sha256')
                assert base64.b64decode(proof) == bytes(a ^ b for a, b in zip(client_key, signature))
                server_sig = hmac.digest(hmac.digest(salted, b'Server Key', 'sha256'), auth, 'sha256')
                if self.bad_signature:
                    server_sig = b'x' * 32
                self.input += (packet(b'R', struct.pack('!I', 12) + b'v=' + base64.b64encode(server_sig))
                    + packet(b'R', struct.pack('!I', 0)) + packet(b'K', struct.pack('!II', 103, 0))
                    + packet(b'S', b'client_encoding\0UTF8\0') + packet(b'Z', b'I'))
        else:
            self.input += packet(b'R', struct.pack('!I', self.auth) + (b'SCRAM-SHA-256\0\0' if self.auth == 10 else b''))


@pytest.fixture
def wire(monkeypatch, campaign, tls_material):
    wire = ScriptedSocket(campaign, tls_material[1])
    created, wrapped = [], []
    def create(*args):
        created.append(args)
        assert len(created) == 1
        return wire
    def wrap(context, raw, **kwargs):
        assert raw is wire and kwargs == dict(server_hostname=campaign.host, do_handshake_on_connect=False)
        assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
        wrapped.append(raw)
        return wire
    monkeypatch.setattr(t.socket, 'socket', create)
    monkeypatch.setattr(ssl.SSLContext, 'wrap_socket', wrap)
    return wire


def opening(campaign, policy):
    return dict(host=campaign.host, port=5432, database=campaign.database, role=campaign.roles[2],
        password=PRIVATE, ca_der=policy.trusted_ca_der, timeout=3, options=t.OPTIONS)


def test_single_socket_sql_identity_and_binding(campaign, policy, wire):
    transport = t.ReadOnlyPostgresTransport(campaign, policy)
    connection = transport.open_readonly(**opening(campaign, policy))
    binding = transport.tls_binding(connection)
    assert type(binding) is c.TlsBinding and binding.connection is connection
    assert binding.certificate_der == wire.certificate and binding.socket_id == 42
    assert binding.driver_verified and binding.auth_method == 'scram-sha-256'
    assert not connection.real_attested and not connection.execution_authorized
    assert PRIVATE.encode() not in b''.join(wire.sent)
    assert PRIVATE not in repr(connection) + repr(transport) + repr(binding)
    startup = wire.sent[1]
    assert t.OPTIONS.encode() in startup and b'UTF8' in startup
    cursor = connection.cursor()
    cursor.execute(c.IDENTITY_SQL)
    assert cursor.fetchone() == wire.identity and cursor.fetchone() is None
    cursor.close()
    connection.rollback()
    connection.close()
    connection.close()
    assert wire.closed == 1
    with pytest.raises(Rejected): transport.tls_binding(connection)
    with pytest.raises(ExecutionDisabled): bool(transport)


@pytest.mark.parametrize('change', [dict(host='localhost'), dict(port=5434), dict(database='industrial_predict_dev'),
    dict(role='postgres'), dict(ca_der=b'invalid'), dict(timeout=0), dict(timeout=float('nan')),
    dict(timeout=True), dict(options='sslmode=disable'), dict(password=''), dict(password='non-ascii-\u00e9'),
    dict(password='line\nbreak')])
def test_invalid_parameters_never_open_socket(campaign, policy, monkeypatch, change):
    calls = []
    def forbidden(*args):
        calls.append(args)
        raise AssertionError('socket must not be created')
    monkeypatch.setattr(t.socket, 'socket', forbidden)
    with pytest.raises(Rejected):
        t.ReadOnlyPostgresTransport(campaign, policy).open_readonly(**(opening(campaign, policy) | change))
    assert not calls


def test_invalid_ca_parsing_precedes_socket(campaign, policy, monkeypatch):
    bad = b'not a DER certificate'
    campaign = replace(campaign, ca_sha256=hashlib.sha256(bad).hexdigest())
    policy = replace(policy, trusted_ca_der=bad)
    calls = []
    def forbidden(*args):
        calls.append(args)
        raise AssertionError('socket must not be created')
    monkeypatch.setattr(t.socket, 'socket', forbidden)
    with pytest.raises(Rejected):
        t.ReadOnlyPostgresTransport(campaign, policy).open_readonly(**opening(campaign, policy))
    assert not calls


@pytest.mark.parametrize('field,value', [('database', 'other'), ('session_role', 'postgres'), ('role', 'postgres'),
    ('address', '127.0.0.1'), ('port', 5434), ('cluster', 'other'), ('instance', 'other'),
    ('version', '170009'), ('pid', 104), ('elevated', True), ('dev_marker', 'dev'),
    ('read_only', 'off'), ('default_read_only', 'off')])
def test_sql_destination_mismatch_closes(campaign, policy, wire, field, value):
    wire.identity[field] = value
    with pytest.raises(Rejected):
        t.ReadOnlyPostgresTransport(campaign, policy).open_readonly(**opening(campaign, policy))
    assert wire.closed == 1


@pytest.mark.parametrize('code', [0, 3, 5, 11, 12])
def test_unverified_or_wrong_authentication_refused(campaign, policy, wire, code):
    wire.auth = code
    with pytest.raises(Rejected):
        t.ReadOnlyPostgresTransport(campaign, policy).open_readonly(**opening(campaign, policy))
    assert wire.closed == 1 and len(wire.sent) == 2


@pytest.mark.parametrize('fault', ['ssl_refusal', 'bad_signature', 'handshake', 'oversize', 'eof', 'server_error'])
def test_protocol_failures_close_and_sanitize(campaign, policy, wire, fault):
    if fault == 'ssl_refusal': wire.ssl_reply = b'N'
    if fault == 'bad_signature': wire.bad_signature = True
    if fault == 'handshake': wire.handshake_error = ssl.SSLCertVerificationError(PRIVATE)
    if fault == 'oversize': wire.query_results[c.IDENTITY_SQL] = b'T' + struct.pack('!I', 2**30)
    if fault == 'eof': wire.query_results[c.IDENTITY_SQL] = b''
    if fault == 'server_error': wire.query_results[c.IDENTITY_SQL] = packet(b'E', PRIVATE.encode())
    with pytest.raises(Rejected) as caught:
        t.ReadOnlyPostgresTransport(campaign, policy).open_readonly(**opening(campaign, policy))
    assert wire.closed == 1
    assert PRIVATE not in ''.join(traceback.format_exception(caught.value))
    assert caught.value.__context__ is None and caught.value.__cause__ is None


def test_only_fixed_metadata_queries_and_closed_on_error(campaign, policy, wire):
    connection = t.ReadOnlyPostgresTransport(campaign, policy).open_readonly(**opening(campaign, policy))
    with pytest.raises(Rejected): connection.cursor().execute('DROP TABLE anything')
    assert wire.closed == 1
    assert not any(b'DROP TABLE' in data for data in wire.sent)


def test_foreign_binding_and_peer_changes_refused(campaign, policy, wire):
    first, second = t.ReadOnlyPostgresTransport(campaign, policy), t.ReadOnlyPostgresTransport(campaign, policy)
    connection = first.open_readonly(**opening(campaign, policy))
    with pytest.raises(Rejected): second.tls_binding(connection)
    wire.certificate = b'changed'
    with pytest.raises(Rejected): first.tls_binding(connection)
    connection.close()


def test_deadline_expiry_and_cleanup_error_are_sanitized(campaign, policy, wire, monkeypatch):
    transport = t.ReadOnlyPostgresTransport(campaign, policy)
    connection = transport.open_readonly(**opening(campaign, policy))
    monkeypatch.setattr(t, 'monotonic', lambda: connection._deadline + 1)
    with pytest.raises(Rejected): connection.rollback()
    assert wire.closed == 1


def test_close_failure_attempted_once_and_sanitized(campaign, policy, wire, monkeypatch):
    connection = t.ReadOnlyPostgresTransport(campaign, policy).open_readonly(**opening(campaign, policy))
    def failed_close():
        wire.closed += 1
        raise OSError(PRIVATE)
    monkeypatch.setattr(wire, 'close', failed_close)
    with pytest.raises(Rejected) as caught:
        connection.close()
    assert PRIVATE not in ''.join(traceback.format_exception(caught.value))
    connection.close()  # Never retry an ambiguously closed descriptor.
    assert wire.closed == 1


def test_scram_rfc7677_known_answer():
    # RFC 7677 section 3: independent published vector, not a simulated TLS claim.
    scram = t._Scram('pencil')
    scram._nonce = b'rOprNGfwEbeRWgbNEkqO'
    scram._first = b'n=user,r=' + scram._nonce
    nonce = scram._nonce + b'%hvYDpWUa2RaTCAfuxFIlj)hNlF$k0'
    challenge = b'r=' + nonce + b',s=W22ZaJ0SNY7soEsUEjb6gQ==,i=4096'
    assert scram.continue_(challenge) == (b'c=biws,r=' + nonce
        + b',p=dHzbZapWIk4jUhN+Ute9ytag9zjfMHgsqmmiz7AndVQ=')
    scram.finish(b'v=6rriTRBi23WpRR/wtup+mMhUZUn/dB5nLTJRsjl95G4=')


def test_scram_bounds_before_key_derivation():
    for suffix in (b',s=b2ZmbGluZS1zYWx0,i=4095', b',s=b2ZmbGluZS1zYWx0,i=100001',
                   b',s=not-base64,i=4096', b',s=eA==,i=4096'):
        scram = t._Scram(PRIVATE)
        with pytest.raises(ValueError):
            scram.continue_(b'r=' + scram._nonce + b'extension' + suffix)


def test_collector_integration_with_scripted_wire(campaign, policy, wire):
    privileges = dict(schema_usage=True, schema_create=False, database_create=False, database_temp=False,
        role_memberships=0, session_select=True, session_insert=True, session_delete=False,
        sequence_usage=False, users_select=True, identities_select=True, business_write=False)
    columns = [dict(table_name=table, column_name=column, can_update=column in allowed)
        for table, names, allowed in (
            ('application_sessions', ('secret_digest', 'last_activity_at', 'replaced_by', 'revoked_at'),
                {'last_activity_at', 'replaced_by', 'revoked_at'}),
            ('local_users', ('id', 'state'), {'id'}),
            ('external_identities', ('id', 'user_id'), {'id'})) for column in names]
    for query in ('BEGIN TRANSACTION READ ONLY', "SET LOCAL statement_timeout='3s'", "SET LOCAL lock_timeout='1s'"):
        wire.query_results[query] = packet(b'C', b'OK\0') + packet(b'Z', b'T')
    wire.query_results[c.REVISION_SQL] = result([{'version_num': 'b2b_0002_analyze'}])
    wire.query_results[c.PRIVILEGES_SQL] = result([privileges])
    wire.query_results[c.COLUMNS_SQL] = result(columns)
    transport = t.ReadOnlyPostgresTransport(campaign, policy)
    packets = c.PostgresCollector(campaign, policy, transport=transport).collect(
        c.SqlCredentials(campaign.roles[2], PRIVATE), revision='b2b_0002_analyze')
    assert len(packets) == 2 and wire.closed == 1
    assert packets[0].observation.connection_id == packets[1].observation.connection_id
    assert dict(packets[0].observation.facts)['backend_pid'] == '103'
    assert packets[1].certificate_der == wire.certificate
    assert not packets[0].real_attested and not packets[0].execution_authorized


@pytest.mark.parametrize('message', [b'r=wrong,s=b2ZmbGluZS1zYWx0,i=4096',
    b'r=x,s=eA==,i=4096', b'm=required,r=x,s=eA==,i=4096'])
def test_scram_rejects_malformed_challenge(message):
    with pytest.raises(ValueError): t._Scram(PRIVATE).continue_(message)
