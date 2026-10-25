"""Pair transaction coordinator. B-1 tests use simulated sessions only."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json

from app.p101_postgres.guard import check_destination
from app.p101_postgres.mapping import instant, map_prediction, validate_dossier, validate_sources
from app.p101_postgres.repository import P101Repository
from app.p101_postgres.runtime import ContentConflict, GuardRejected, PersistenceError, dossier_fingerprint
from app.p101_postgres.session import create_session_factory


@dataclass(frozen=True)
class BatchReceipt:
    status: str
    keys: tuple[str, ...]
    dossier_sha256: str
    persistence_revision: str
    records_json: str = "[]"

    @property
    def records(self):
        return json.loads(self.records_json)


def sqlstate(error):
    return getattr(getattr(error, "orig", error), "sqlstate", None)


class P101PersistenceService:
    def __init__(self, config, verifier, *, session_factory=None, repository_factory=P101Repository,
                 guard=check_destination, clock=lambda: datetime.now(timezone.utc)):
        self.config, self.verifier = config, verifier
        self._factory = session_factory
        self._repository_factory, self._guard, self._clock = repository_factory, guard, clock

    def _session(self):
        if self._factory is None:
            self._factory = create_session_factory(self.config)
        session = self._factory()
        if session.in_transaction() or session.new or session.dirty or session.deleted:
            session.close()
            raise GuardRejected("A fresh dedicated session is required")
        return session

    def _validate(self, dossier, approval):
        validate_dossier(dossier)
        self.verifier.verify(approval, dossier, self.config, self._clock())

    def _receipt(self, status, dossier, rows=()):
        return BatchReceipt(status, tuple(t.key.projection.sha256 for t in dossier.targets),
            dossier_fingerprint(dossier), self.config.persistence_revision,
            json.dumps(list(rows), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))

    @staticmethod
    def _rollback(session):
        try:
            session.rollback()
        except Exception:
            raise PersistenceError("Rollback could not be confirmed") from None

    @staticmethod
    def _close(session):
        try:
            session.close()
        except Exception:
            pass  # Cleanup failure cannot turn a known successful commit into failure.

    def persist(self, dossier, approval):
        for attempt in range(3):
            self._validate(dossier, approval)
            session = self._session()
            commit_started = False
            try:
                transaction = session.begin()
                self._guard(session, self.config)  # Before lock/sequence/reservation/INSERT.
                repository = self._repository_factory(session)
                sources = validate_sources(dossier, repository.lock_sources())
                # clock_timestamp returns an aware datetime; no fabricated persistence time.
                created_at = instant(repository.clock())
                reservations, rows = [], []
                for target in sorted(dossier.targets, key=lambda t: t.key.projection.sha256):
                    prediction_id = repository.next_id()
                    new, ledger = repository.reserve(target, prediction_id, created_at)
                    reservations.append(new)
                    if new:
                        rows.append((target, map_prediction(dossier, target, sources, prediction_id, created_at)))
                    else:
                        rows.append((target, repository.existing(dossier, target, sources, ledger)))
                if len(set(reservations)) != 1:
                    raise ContentConflict("Partially existing P101 pair")
                if all(reservations):
                    for _, row in rows:
                        repository.insert_prediction(row)
                repository.check_constraints()
                rows.sort(key=lambda item: item[0].identity)
                receipt = self._receipt("created" if all(reservations) else "existing", dossier,
                                        [row for _, row in rows])
                # Approval is checked again immediately before committing the pair.
                self.verifier.verify(approval, dossier, self.config, self._clock())
                commit_started = True
                transaction.commit()
                return receipt
            except Exception as error:
                state = sqlstate(error)
                known_abort = (isinstance(state, str) and state.startswith("23")) or state in ("40001", "40P01")
                if commit_started and not known_abort:
                    return self._receipt("commit_unknown", dossier)
                self._rollback(session)
                if state in ("40001", "40P01") and attempt < 2:
                    continue
                if isinstance(error, PersistenceError):
                    raise
                raise PersistenceError("P101 transaction rejected before a confirmed commit") from None
            finally:
                self._close(session)

    def resolve(self, dossier, approval):
        """Read-only resolution in a new guarded transaction, never an auto-insert."""
        self._validate(dossier, approval)
        session = self._session()
        try:
            session.begin()
            self._guard(session, self.config)
            repository = self._repository_factory(session)
            sources = validate_sources(dossier, repository.lock_sources())
            ledgers = [repository.find(t) for t in dossier.targets]
            if all(row is None for row in ledgers):
                return self._receipt("not_observed", dossier)
            if any(row is None for row in ledgers):
                raise ContentConflict("Partially observed P101 pair")
            rows = [repository.existing(dossier, target, sources, row)
                    for target, row in zip(dossier.targets, ledgers)]
            return self._receipt("existing", dossier, rows)
        except PersistenceError:
            raise
        except Exception:
            return self._receipt("resolution_unavailable", dossier)
        finally:
            try:
                session.rollback()
            finally:
                self._close(session)
