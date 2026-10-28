"""OIDC transaction core, without HTTP, persistence adapter or token validation.

Stores are trusted injected adapters. Their confirmation is a contractual promise
of a completed commit, not something Python can verify independently. Raw start
values are for controlled backend transport only, never an Angular JSON payload.
"""

import base64
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import hmac
import json
import re
import secrets
from typing import Literal, Protocol

from app.core.oidc_config import OidcConfig


CONTRACT_VERSION = "oidc-transaction-v1"
POLICY_VERSION = "oidc-transaction-policy-v1"
PKCE_METHOD = "S256"


class TransactionError(ValueError):
    CODE = "OIDC_TRANSACTION_ERROR"

    def __init__(self):
        super().__init__(self.CODE)


class InvalidTransactionInput(TransactionError):
    CODE = "OIDC_TRANSACTION_INPUT_INVALID"


class TransactionRejected(TransactionError):
    CODE = "OIDC_TRANSACTION_REJECTED"


class TransactionCollision(TransactionError):
    CODE = "OIDC_TRANSACTION_COLLISION"


class TransactionStoreUnavailable(TransactionError):
    CODE = "OIDC_TRANSACTION_STORE_UNAVAILABLE"


class TransactionCommitUncertain(TransactionError):
    CODE = "OIDC_TRANSACTION_COMMIT_UNCERTAIN"


class TransactionStoreInvalid(TransactionError):
    CODE = "OIDC_TRANSACTION_STORE_INVALID"


class TransactionGenerationFailed(TransactionError):
    CODE = "OIDC_TRANSACTION_GENERATION_FAILED"


@dataclass(frozen=True, slots=True, repr=False)
class OidcTransaction:
    transaction_id: str
    state_digest: str
    browser_binding_digest: str
    nonce: str
    code_verifier: str
    issuer: str
    client_id: str
    callback_url: str
    policy_digest: str
    return_target: str
    created_at: datetime
    expires_at: datetime
    contract_version: str = CONTRACT_VERSION


@dataclass(frozen=True, slots=True, repr=False)
class TransactionStart:
    """Transport material for backend redirect/cookie code, not a public DTO.

    No code_verifier is returned. nonce goes to the authorization endpoint;
    browser_binding goes only to the future HttpOnly binding cookie.
    """

    transaction_id: str
    state: str
    nonce: str
    browser_binding: str
    code_challenge: str
    expires_at: datetime
    code_challenge_method: Literal["S256"] = PKCE_METHOD


@dataclass(frozen=True, slots=True, repr=False)
class ConsumptionCondition:
    state_digest: str
    browser_binding_digest: str
    policy_digest: str
    now: datetime
    contract_version: str = CONTRACT_VERSION


class InsertStatus(Enum):
    CONFIRMED = "confirmed"
    COLLISION = "collision"
    UNCERTAIN = "uncertain"


class ConsumeStatus(Enum):
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True, slots=True, repr=False)
class ConsumptionReceipt:
    status: ConsumeStatus
    transaction: OidcTransaction | None = None


class TransactionStore(Protocol):
    """Atomic insert/consume port; no separate read-and-delete operation.

    insert_new must never replace a matching transaction_id OR state_digest.
    consume must atomically match every condition and created_at <= now <
    expires_at, then irreversibly remove/mark the record. Exactly one concurrent
    consumer may win. Mismatch must leave the legitimate record untouched.
    Return CONFIRMED and its context ONLY after commit confirmation. No secret
    context on REJECTED/UNCERTAIN. Commit uncertainty must be reported explicitly
    (status or TransactionCommitUncertain), never as a confirmed operation.
    Expired-record purge is optional adapter housekeeping, not validity logic.
    """

    def insert_new(self, transaction: OidcTransaction) -> InsertStatus:
        ...

    def consume(self, condition: ConsumptionCondition) -> ConsumptionReceipt:
        ...


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _token(value: object) -> bool:
    # Generated 32-byte tokens have a unique canonical 43-character encoding.
    if type(value) is not str or re.fullmatch(r"[A-Za-z0-9_-]{43}", value) is None:
        return False
    return _b64(base64.urlsafe_b64decode(value + "=")) == value


def _digest(label: str, value: str) -> str:
    return hashlib.sha256((label + "\0" + value).encode("ascii")).hexdigest()


def _utc(value: object) -> bool:
    return type(value) is datetime and value.tzinfo is not None and value.utcoffset() == timedelta(0)


def pkce_s256(code_verifier: str) -> str:
    """RFC 7636 S256 transform only. Accept the standard verifier alphabet."""
    if (type(code_verifier) is not str
            or re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", code_verifier) is None):
        raise InvalidTransactionInput()
    return _b64(hashlib.sha256(code_verifier.encode("ascii")).digest())


def _config(config: OidcConfig) -> OidcConfig:
    valid = None
    if type(config) is OidcConfig:
        try:
            valid = OidcConfig.model_validate(dict(config))
        except Exception:
            pass
    if valid is None:
        raise InvalidTransactionInput() from None
    return valid


def _targets(values: tuple[str, ...]) -> tuple[str, ...]:
    if (type(values) is not tuple or not values
            or any(type(value) is not str or re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", value) is None
                   for value in values)
            or len(set(values)) != len(values)):
        raise InvalidTransactionInput()
    return values


def transaction_policy_digest(config: OidcConfig, *, allowed_return_targets: tuple[str, ...]) -> str:
    """Canonical UTF-8 JSON: sorted keys, compact separators, exact identifiers.

    Covers all OidcConfig fields, sorted signature algorithms, sorted permitted
    return symbols, policy/contract versions and mandatory PKCE method. No raw
    state, binding, nonce or verifier occurs in this public policy material.
    """
    config = _config(config)
    targets = _targets(allowed_return_targets)
    data = config.model_dump()
    data["signature_algorithms"] = sorted(config.signature_algorithms)
    policy = dict(policy_version=POLICY_VERSION, contract_version=CONTRACT_VERSION,
                  pkce_method=PKCE_METHOD, config=data, allowed_return_targets=sorted(targets))
    canonical = json.dumps(policy, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class OidcTransactionManager:
    """No I/O except explicit port calls; clock required, CSPRNG used on create.

    Deterministic randomness may only be substituted by tests patching the CSPRNG.
    No memory store, mutable global registry or protocol retry is provided here.
    """

    def __init__(self, *, config: OidcConfig, store: TransactionStore,
                 clock: Callable[[], datetime], allowed_return_targets: tuple[str, ...]):
        self._config = _config(config)
        self._targets = _targets(allowed_return_targets)
        if not callable(clock):
            raise InvalidTransactionInput()
        valid_store = False
        try:
            valid_store = callable(store.insert_new) and callable(store.consume)
        except Exception:
            pass
        if not valid_store:
            raise InvalidTransactionInput()
        self._store = store
        self._clock = clock

    def _now(self) -> datetime:
        now = None
        try:
            now = self._clock()
            if not _utc(now):
                now = None
        except Exception:
            pass
        if now is None:
            raise InvalidTransactionInput() from None
        return now

    def create(self, *, return_target: str) -> TransactionStart:
        if type(return_target) is not str or return_target not in self._targets:
            raise InvalidTransactionInput()
        now = self._now()
        config = _config(self._config)
        policy = transaction_policy_digest(config, allowed_return_targets=self._targets)
        expires = None
        try:
            expires = now + timedelta(seconds=config.transaction_ttl_seconds)
        except OverflowError:
            pass
        if expires is None:
            raise InvalidTransactionInput()
        tokens = None
        try:
            draws = tuple(secrets.token_bytes(32) for _ in range(4))
            if all(type(draw) is bytes and len(draw) == 32 for draw in draws) and len(set(draws)) == 4:
                tokens = tuple(_b64(draw) for draw in draws)
        except Exception:
            pass
        if tokens is None:
            raise TransactionGenerationFailed() from None
        state, nonce, verifier, binding = tokens
        tx = OidcTransaction(
            transaction_id=_digest("oidc-transaction-id-v1", state),
            state_digest=_digest("oidc-state-v1", state),
            browser_binding_digest=_digest("oidc-browser-v1", binding), nonce=nonce, code_verifier=verifier,
            issuer=config.issuer, client_id=config.client_id, callback_url=config.callback_url,
            policy_digest=policy, return_target=return_target, created_at=now,
            expires_at=expires,
        )
        status = None
        failed = False
        try:
            status = self._store.insert_new(tx)
        except TransactionCommitUncertain:
            status = InsertStatus.UNCERTAIN
        except Exception:
            failed = True
        if failed:
            raise TransactionStoreUnavailable() from None
        if status is InsertStatus.UNCERTAIN:
            raise TransactionCommitUncertain() from None
        if status is InsertStatus.COLLISION:
            raise TransactionCollision()
        if status is not InsertStatus.CONFIRMED:
            raise TransactionStoreInvalid()
        return TransactionStart(tx.transaction_id, state, nonce, binding, pkce_s256(verifier), tx.expires_at)

    def consume(self, *, state: str, browser_binding: str,
                callback_outcome: Literal["code", "provider_error"] = "code") -> OidcTransaction | None:
        """Only correlated callbacks may terminate. Provider error returns no secrets.

        No authorization code/token is accepted here. A confirmed context for the
        'code' outcome is backend-only input to a later OIDC client, not identity.
        """
        if (not _token(state) or not _token(browser_binding)
                or type(callback_outcome) is not str or callback_outcome not in ("code", "provider_error")):
            raise TransactionRejected()
        now = self._now()
        config = _config(self._config)
        condition = ConsumptionCondition(
            _digest("oidc-state-v1", state), _digest("oidc-browser-v1", browser_binding),
            transaction_policy_digest(config, allowed_return_targets=self._targets), now,
        )
        receipt = None
        failed = uncertain = False
        try:
            receipt = self._store.consume(condition)
        except TransactionCommitUncertain:
            uncertain = True
        except Exception:
            failed = True
        if uncertain:
            raise TransactionCommitUncertain() from None
        if failed:
            raise TransactionStoreUnavailable() from None
        if type(receipt) is not ConsumptionReceipt:
            raise TransactionStoreInvalid()
        status = transaction = None
        try:
            status, transaction = receipt.status, receipt.transaction
        except AttributeError:
            pass
        if status is ConsumeStatus.UNCERTAIN:
            raise TransactionCommitUncertain()
        if status is ConsumeStatus.REJECTED and transaction is None:
            raise TransactionRejected()
        if (status is not ConsumeStatus.CONFIRMED
                or not self._matches(transaction, condition, config, _digest("oidc-transaction-id-v1", state))):
            raise TransactionStoreInvalid()
        return transaction if callback_outcome == "code" else None

    def _matches(self, tx: OidcTransaction, expected: ConsumptionCondition,
                 config: OidcConfig, transaction_id: str) -> bool:
        # Defence in depth against malformed receipts; atomicity still belongs to
        # the adapter. A bad confirmed receipt is never restored/retried here.
        if type(tx) is not OidcTransaction:
            return False
        try:
            return (
                all(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None for value in
                    (tx.transaction_id, tx.state_digest, tx.browser_binding_digest, tx.policy_digest))
                and hmac.compare_digest(tx.transaction_id, transaction_id)
                and hmac.compare_digest(tx.state_digest, expected.state_digest)
                and hmac.compare_digest(tx.browser_binding_digest, expected.browser_binding_digest)
                and hmac.compare_digest(tx.policy_digest, expected.policy_digest)
                and _token(tx.nonce) and _token(tx.code_verifier)
                and type(tx.contract_version) is str and tx.contract_version == CONTRACT_VERSION
                and all(type(value) is str for value in (tx.issuer, tx.client_id, tx.callback_url))
                and (tx.issuer, tx.client_id, tx.callback_url) == (config.issuer, config.client_id, config.callback_url)
                and type(tx.return_target) is str and tx.return_target in self._targets
                and _utc(tx.created_at) and _utc(tx.expires_at)
                and tx.expires_at - tx.created_at == timedelta(seconds=config.transaction_ttl_seconds)
                and tx.created_at <= expected.now < tx.expires_at
            )
        except (AttributeError, TypeError, ValueError):
            return False
