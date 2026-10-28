"""Explicit PostgreSQL TransactionStore; no HTTP, engine or import-time I/O.

Each call owns a fresh runtime session and its commit. READ COMMITTED applies
only to that checked-out connection; SQLAlchemy resets isolation on pool return.
Lock/statement waits are bounded at 5/15 seconds, and timeouts are store failures.

Consumption requires BOTH condition.now and a PostgreSQL clock_timestamp()
sample taken in a separate command AFTER FOR UPDATE returns. Expiry is exclusive.
Expiry while waiting rejects; expiry after this decision, during commit, is
admissible. Clocks must be synchronized by deployment. No network service other
than the explicitly injected database is called, and no retry is performed.

The role needs INSERT/SELECT/DELETE plus UPDATE on at least one column for
FOR UPDATE (a column grant, e.g. transaction_id, suffices). No UPDATE is executed.
Deployment must protect transport, server logs, backups and recoverable verifier
storage; this module never logs driver exceptions or values. No migration or
purge executor is installed here.
"""

import base64
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import logging
import re
from typing import TypeVar

from sqlalchemy import delete, func, insert, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database_runtime import SqlRuntime
from app.core.oidc_transactions import (
    ConsumptionCondition, ConsumptionReceipt, ConsumeStatus, InsertStatus,
    OidcTransaction, TransactionCommitUncertain, TransactionStoreUnavailable,
)
from app.models.oidc_transaction import OidcTransactionRecord


_TABLE = OidcTransactionRecord.__table__
_UNIQUE_CONSTRAINTS = frozenset(("pk_oidc_transactions", "uq_oidc_transactions_state_digest"))
_T = TypeVar("_T")


def _utc(value: object) -> bool:
    return (type(value) is datetime and value.tzinfo is not None
            and value.utcoffset() == timedelta(0))


def _hex(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _token(value: object) -> bool:
    if type(value) is not str or re.fullmatch(r"[A-Za-z0-9_-]{43}", value) is None:
        return False
    raw = base64.urlsafe_b64decode(value + "=")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii") == value


def _valid_transaction(tx: OidcTransaction) -> bool:
    return (
        type(tx) is OidcTransaction
        and all(_hex(getattr(tx, field)) for field in
                ("transaction_id", "state_digest", "browser_binding_digest", "policy_digest"))
        and _token(tx.nonce) and _token(tx.code_verifier)
        and all(type(value) is str and 0 < len(value) <= limit for value, limit in
                ((tx.issuer, 2048), (tx.client_id, 512), (tx.callback_url, 2048), (tx.return_target, 64)))
        and type(tx.contract_version) is str and bool(tx.contract_version)
        and _utc(tx.created_at) and _utc(tx.expires_at) and tx.created_at < tx.expires_at
    )


def _collision(error: Exception) -> bool:
    return (isinstance(error, IntegrityError)
            and getattr(error.orig, "sqlstate", None) == "23505"
            and getattr(getattr(error.orig, "diag", None), "constraint_name", None) in _UNIQUE_CONSTRAINTS)


class PostgresTransactionStore:
    """Trusted private adapter; an external session/transaction is never accepted."""

    def __init__(self, runtime: SqlRuntime):
        if type(runtime) is not SqlRuntime:
            raise TransactionStoreUnavailable()
        self._runtime = runtime

    def _run(self, operation: Callable[[Session], _T], *, insertion: bool = False) -> _T | InsertStatus:
        outcome = "unavailable"
        result = None
        committed = False
        try:
            engine = self._runtime.engine
            # DEBUG engine logging can print RETURNING rows despite parameter
            # hiding. Refuse unsafe logging; never mutate the shared engine.
            if engine.echo or not engine.hide_parameters or engine.logger.isEnabledFor(logging.DEBUG):
                raise TransactionStoreUnavailable()
            with self._runtime.session() as db:
                phase = "work"
                try:
                    db.connection(execution_options={"isolation_level": "READ COMMITTED"})
                    db.execute(text("SET LOCAL lock_timeout = '5s'"))
                    db.execute(text("SET LOCAL statement_timeout = '15s'"))
                    result = operation(db)
                    phase = "commit"
                    db.commit()
                    committed = True
                except Exception as error:
                    # Every commit exception is conservatively uncertain; even
                    # a successful subsequent rollback cannot disprove commit.
                    if phase == "commit":
                        outcome = "uncertain"
                    elif insertion and _collision(error):
                        outcome = "collision"
                    try:
                        db.rollback()
                    except Exception:
                        pass
        except Exception:
            # Acquisition/close failures must not leak driver context. A close
            # error cannot undo a commit that has already been acknowledged.
            pass
        if committed:
            return result
        if outcome == "collision":
            return InsertStatus.COLLISION
        if outcome == "uncertain":
            raise TransactionCommitUncertain()
        # Raised outside handlers so __context__ does not retain driver data.
        raise TransactionStoreUnavailable()

    def insert_new(self, transaction: OidcTransaction) -> InsertStatus:
        valid = False
        try:
            valid = _valid_transaction(transaction)
        except Exception:
            pass
        # Raise outside the handler so sensitive validation context is discarded.
        if not valid:
            raise TransactionStoreUnavailable()

        def operation(db: Session) -> InsertStatus:
            db.execute(insert(_TABLE).values(**asdict(transaction)))
            return InsertStatus.CONFIRMED

        return self._run(operation, insertion=True)

    def consume(self, condition: ConsumptionCondition) -> ConsumptionReceipt:
        valid = False
        try:
            valid = (
                type(condition) is ConsumptionCondition
                and all(_hex(value) for value in
                        (condition.state_digest, condition.browser_binding_digest, condition.policy_digest))
                and _utc(condition.now) and type(condition.contract_version) is str
                and bool(condition.contract_version)
            )
        except Exception:
            pass
        # Raise outside the handler so sensitive validation context is discarded.
        if not valid:
            raise TransactionStoreUnavailable()

        def operation(db: Session) -> ConsumptionReceipt:
            c = _TABLE.c
            predicates = (
                c.state_digest == condition.state_digest,
                c.browser_binding_digest == condition.browser_binding_digest,
                c.policy_digest == condition.policy_digest,
                c.contract_version == condition.contract_version,
                c.created_at <= condition.now,
                c.expires_at > condition.now,
            )
            identifier = db.execute(select(c.transaction_id).where(*predicates).with_for_update()).scalar_one_or_none()
            if identifier is None:
                return ConsumptionReceipt(ConsumeStatus.REJECTED)
            # Separate round trip: never sample before or inside the lock query.
            decision = db.execute(select(func.clock_timestamp())).scalar_one()
            if type(decision) is not datetime or decision.tzinfo is None or decision.utcoffset() is None:
                raise TransactionStoreUnavailable()
            decision = decision.astimezone(timezone.utc)
            row = db.execute(delete(_TABLE).where(
                *predicates, c.transaction_id == identifier,
                c.created_at <= decision, c.expires_at > decision,
            ).returning(*c)).mappings().one_or_none()
            if row is None:
                return ConsumptionReceipt(ConsumeStatus.REJECTED)
            values = dict(row)
            for name in ("created_at", "expires_at"):
                value = values[name]
                if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
                    raise TransactionStoreUnavailable()
                values[name] = value.astimezone(timezone.utc)
            tx = OidcTransaction(**values)
            if not _valid_transaction(tx):
                raise TransactionStoreUnavailable()
            return ConsumptionReceipt(ConsumeStatus.CONFIRMED, tx)

        return self._run(operation)
