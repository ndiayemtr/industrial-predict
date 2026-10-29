#!/usr/bin/env bash
# Preparation artifact: no configuration, argument or environment enables it.
printf '%s\n' 'OIDC bootstrap operational authority is unavailable' >&2
exit 78

# Unreachable phase drafts for independent review. No dispatcher is installed.
# A future authority and live attester must be reviewed before any activation.
set -Eeuo pipefail
umask 077
ROOT=/var/lib/postgresql/data
DATA="$ROOT/pgdata"
WORK="$ROOT/work"
SOCKET="$ROOT/run"
SECRETS="$ROOT/secrets"
TLS="$ROOT/tls"

live_gate() {
    printf '%s\n' 'OIDC bootstrap operational authority is unavailable' >&2
    return 78
}

live_postcondition() {
    # A zero process exit code is never a phase attestation.
    printf '%s\n' 'OIDC bootstrap live attestation is unavailable' >&2
    return 78
}

phase_A() {
    live_gate A || return 78
    # Future broker: exact identity/version, clean environment, first generation,
    # fresh campaign-only secrets over a private input channel. No env password.
    live_postcondition A
}

phase_B() {
    live_gate B || return 78
    # Gate must inspect mountinfo, size, extra mounts, canonical paths, symlinks,
    # real IDs and freshness BEFORE changing permissions on this exact tmpfs.
    chown postgres:postgres "$ROOT"
    chmod 0700 "$ROOT"
    install -d -m 0700 -o postgres -g postgres "$DATA" "$WORK" "$SOCKET" "$SECRETS" "$TLS" "$ROOT/log"
    live_postcondition B
}

phase_C() {
    live_gate C || return 78
    # Gate must prove empty DATA, PostgreSQL 17.10, password file 0600/nonempty,
    # postgres ownership/traversability, no outside WAL/tablespaces, no TCP.
    /usr/local/bin/gosu postgres /usr/lib/postgresql/17/bin/initdb \
        --pgdata="$DATA" --username="$BOOTSTRAP_ROLE" \
        --auth-local=scram-sha-256 --auth-host=scram-sha-256 \
        --pwfile="$SECRETS/bootstrap.pw"
    live_postcondition C
}

phase_D() {
    live_gate D || return 78
    # Rendered local config/HBA and local.pgpass must be verified independently.
    /usr/local/bin/gosu postgres /usr/lib/postgresql/17/bin/pg_ctl -D "$DATA" \
        -o "-c config_file=$WORK/postgresql.local.conf -c listen_addresses=''" \
        -l "$ROOT/log/local-start.log" -w start
    /usr/local/bin/gosu postgres /usr/bin/env -i \
        PATH=/usr/lib/postgresql/17/bin:/usr/bin:/bin HOME="$WORK" TMPDIR="$WORK" \
        PGHOST="$SOCKET" PGPORT=5432 PGUSER="$BOOTSTRAP_ROLE" PGDATABASE=postgres \
        PGPASSFILE="$SECRETS/local.pgpass" \
        psql -X -w --set ON_ERROR_STOP=1 --file "$WORK/roles.sql"
    # Three campaign roles remain NOLOGIN. No OIDC table or table grant here.
    live_postcondition D
}

phase_E() {
    live_gate E || return 78
    # Future execution only: all key generation stays in the one protected tmpfs.
    openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out "$SECRETS/ca.key"
    openssl req -new -x509 -sha256 -days 1 -key "$SECRETS/ca.key" \
        -subj '/CN=OIDC TEST campaign CA' -addext 'basicConstraints=critical,CA:TRUE' \
        -addext 'keyUsage=critical,keyCertSign,cRLSign' -out "$TLS/ca.crt"
    openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out "$TLS/server.key"
    openssl req -new -key "$TLS/server.key" -config "$WORK/openssl.cnf" -out "$WORK/server.csr"
    openssl x509 -req -sha256 -days 1 -in "$WORK/server.csr" -CA "$TLS/ca.crt" \
        -CAkey "$SECRETS/ca.key" -CAserial "$SECRETS/ca.serial" -CAcreateserial \
        -extfile "$WORK/openssl.cnf" -extensions server_ext -out "$TLS/server.crt"
    chown postgres:postgres "$TLS/server.key" "$TLS/server.crt" "$TLS/ca.crt"
    chmod 0600 "$TLS/server.key"
    # Attest real signature, dates, SAN, key match, CA fingerprint, permissions,
    # exact HBA/source /32 and no plaintext or wildcard allow rule. No TCP yet.
    live_postcondition E
}

phase_F() {
    live_gate F || return 78
    # STOP: no password-installation broker is implemented in this lot.
    # Before this gate can ever pass: install all campaign passwords via a
    # reviewed private channel, enable their LOGIN, disable bootstrap LOGIN,
    # close administrative sessions, verify SQL identities and exact TLS/HBA.
    /usr/local/bin/gosu postgres /usr/lib/postgresql/17/bin/pg_ctl -D "$DATA" -m fast -w stop
    # Only the postmaster stops: PID 1 and the tmpfs must remain alive.
    live_postcondition F || return 78
    exec /usr/local/bin/gosu postgres /usr/lib/postgresql/17/bin/postgres \
        -D "$DATA" -c "config_file=$WORK/postgresql.tls.conf"
}

phase_G() {
    live_gate G || return 78
    # External collector, on real retained client connections: three roles,
    # independent PIDs, SQL/server identity, verify-full and actual source IP.
    # No application DDL follows automatically, even after this attestation.
    live_postcondition G
}
