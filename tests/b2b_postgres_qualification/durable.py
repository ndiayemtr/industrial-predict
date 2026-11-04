"""Temporary-test approval ledger. Fixed SQLite statements, no migration executor."""

from dataclasses import dataclass
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import stat

from b2b_postgres_qualification.authority import ApprovalVerifier, MemoryReplayRegistry
from b2b_postgres_qualification.contracts import Offline, Rejected, deny
from b2b_postgres_qualification import validation as v


class RegistryUncertain(RuntimeError):
    def __init__(self):
        super().__init__("B2B_REGISTRY_UNCERTAIN")


class RegistryCleanupError(RuntimeError):
    """Local cleanup failed; commit_status is metadata, never an execution permit."""
    def __init__(self, phase, commit_status):
        self.phase = phase
        self.commit_status = commit_status
        super().__init__("B2B_REGISTRY_CLEANUP_FAILED")


def _cleanup_error(phase, commit_status):
    try:
        raise RegistryCleanupError(phase, commit_status) from None
    except RegistryCleanupError as error:
        error.__context__ = error.__cause__ = None
        error.__suppress_context__ = True
        raise


def _uncertain():
    try:
        raise RegistryUncertain() from None
    except RegistryUncertain as error:
        error.__context__ = error.__cause__ = None
        error.__suppress_context__ = True
        raise


def _root(directory):
    value = os.fspath(directory)
    v.require(type(value) is str and not value.startswith(("\\\\", "//")))
    root = Path(value)
    v.require(root.is_absolute() and root.name.startswith("b2bq-registry-"))
    v.require(not any(part.casefold() in ("dev", "development") or "p101" in part.casefold()
                      or "oidc" in part.casefold() for part in root.parts))
    v.require(all(not p.is_symlink() and not p.is_junction() for p in (root, *root.parents)))
    root = root.resolve(strict=True)
    v.require(root.is_dir() and not root.is_relative_to(Path(__file__).parent.resolve()))
    return root


def _exclusive(path, content):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def _connect(root):
    path = root / "approvals.sqlite3"
    v.require(path.is_file() and not path.is_symlink() and not path.is_junction())
    db = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=5, isolation_level=None)
    try:
        db.execute("PRAGMA busy_timeout=5000")
        db.execute("PRAGMA synchronous=FULL")
        v.require(db.execute("PRAGMA user_version").fetchone() == (1,))
        return db
    except Exception:
        _close(db, commit_status="not_attempted")
        raise


def _close(db, *, commit_status="not_assessed"):
    if db is not None:
        try:
            db.close()
        except Exception:
            _cleanup_error("sqlite_close", commit_status)


def _publish_uncertainty(marker):
    try:
        _exclusive(marker, b"B2B_REGISTRY_UNCERTAIN\n")
    except FileExistsError:
        pass


def _present(path):
    # Do not interpret a permission/I/O error as an absent quarantine.
    try:
        path.stat(follow_symlinks=False)
    except FileNotFoundError:
        return False
    return True


@contextmanager
def _approval_lock(claim):
    """Nonblocking OS lock, always before SQLite; never unlink the lock file.

    Close is the ONLY release operation. A failed close has ambiguous ownership:
    refuse locally, never retry the descriptor and never publish a marker here.
    Only transaction paths, while ownership is established, publish uncertainty.
    """
    path = claim.with_suffix(".lock")
    fd = None
    try:
        v.require(not path.is_symlink() and not path.is_junction())
        fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        v.require(stat.S_ISREG(os.fstat(fd).st_mode))
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        if fd is not None:
            try:
                os.close(fd)
            except Exception:
                _cleanup_error("lock_close", "not_attempted")
        deny(Rejected)
    body_error = None
    try:
        yield
    except BaseException as error:
        body_error = error
        raise
    finally:
        try:
            os.close(fd)
        except Exception:
            status = "uncertain" if isinstance(body_error, RegistryUncertain) else "not_assessed"
            if isinstance(body_error, RegistryCleanupError):
                status = body_error.commit_status
            _cleanup_error("lock_close", status)


@v.guarded
def initialize_test_registry(directory):
    """Explicit initialization in a caller-created empty isolated temporary directory."""
    root = _root(directory)
    v.require(not tuple(root.iterdir()))
    path = root / "approvals.sqlite3"
    _exclusive(path, b"")
    db = sqlite3.connect(path, timeout=5, isolation_level=None)
    commit_status = "not_attempted"
    try:
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("BEGIN IMMEDIATE")
        db.execute("CREATE TABLE approvals (authority TEXT NOT NULL, approval_id TEXT NOT NULL, campaign TEXT NOT NULL, destination TEXT NOT NULL, envelope TEXT NOT NULL, operation TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('consumed','refused','rollback_confirmed','commit_confirmed','uncertain')), PRIMARY KEY(authority,approval_id))")
        db.execute("CREATE TABLE history (sequence INTEGER PRIMARY KEY, authority TEXT NOT NULL, approval_id TEXT NOT NULL, state TEXT NOT NULL)")
        db.execute("PRAGMA user_version=1")
        commit_status = "uncertain"
        db.commit()
        commit_status = "confirmed"
    finally:
        _close(db, commit_status=commit_status)


@dataclass(frozen=True, slots=True, repr=False)
class RegistryReport(Offline):
    state: str
    campaign_id: str | None
    envelope_sha256: str | None
    history: tuple[str, ...]


class DurableApprovalRegistry(Offline):
    """Single-use reservation + SQLite history; accepted states never authorize SQL."""

    __slots__ = ("_root", "_keys")

    @v.guarded
    def __init__(self, *, directory, trusted_keys):
        self._root = _root(directory)
        # Reuse the fixed crypto path; no favorable verdict object is accepted.
        ApprovalVerifier(trusted_keys=trusted_keys, replay_registry=MemoryReplayRegistry())
        self._keys = trusted_keys
        db = _connect(self._root)
        _close(db)

    def _paths(self, authority_id, approval_id):
        v.text(authority_id)
        v.identifier(approval_id)
        name = sha256((authority_id + "\0" + approval_id).encode("ascii")).hexdigest()
        return self._root / (name + ".claim"), self._root / (name + ".uncertain")

    def _quarantine(self, marker):
        # Caller holds the approval lock, including SQLite failure handling.
        _publish_uncertainty(marker)

    def consume_verified(self, campaign, plan, approval, signed, *, expected_initial_state_sha256, now):
        try:
            claim, _ = self._paths(approval.authority_id, signed.approval_id)
        except Exception:
            deny(Rejected)
        with _approval_lock(claim):
            return self._consume_locked(campaign, plan, approval, signed,
                expected_initial_state_sha256=expected_initial_state_sha256, now=now)

    def _consume_locked(self, campaign, plan, approval, signed, *, expected_initial_state_sha256, now):
        """Reverify the actual signature before any reservation; never trust SignatureReview."""
        try:
            result = ApprovalVerifier(trusted_keys=self._keys, replay_registry=MemoryReplayRegistry()).verify(
                campaign, plan, approval, signed, expected_initial_state_sha256=expected_initial_state_sha256, now=now)
            claim, uncertain = self._paths(approval.authority_id, signed.approval_id)
            v.require(not _present(uncertain))
            content = json.dumps(dict(campaign=campaign.campaign_id, envelope=result.envelope_sha256),
                                 sort_keys=True, separators=(",", ":")).encode("ascii")
            try:
                _exclusive(claim, content)
            except FileExistsError:
                deny(Rejected)
            except Exception:
                if _present(claim):
                    try:
                        self._quarantine(uncertain)
                    except Exception:
                        pass
                    _uncertain()
                deny(Rejected)
        except RegistryUncertain:
            raise
        except Rejected:
            raise
        except Exception:
            deny(Rejected)
        db = None
        commit_status = "not_attempted"
        try:
            db = _connect(self._root)
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO approvals VALUES (?,?,?,?,?,?,?)", (
                approval.authority_id, signed.approval_id, campaign.campaign_id,
                v.destination_fingerprint(campaign), result.envelope_sha256, plan.operation, "consumed"))
            db.execute("INSERT INTO history(authority,approval_id,state) VALUES (?,?,?)", (approval.authority_id, signed.approval_id, "consumed"))
            commit_status = "uncertain"
            db.commit()
            commit_status = "confirmed"
        except Exception:
            # Reservation survives absent/ambiguous SQLite commit; never remove it.
            try:
                self._quarantine(uncertain)
            except Exception:
                pass
            _uncertain()
        finally:
            _close(db, commit_status=commit_status)
        return RegistryReport("consumed", campaign.campaign_id, result.envelope_sha256, ("consumed",))

    @v.guarded
    def inspect(self, *, authority_id, approval_id):
        claim, uncertain = self._paths(authority_id, approval_id)
        with _approval_lock(claim):
            return self._inspect_locked(claim, uncertain, authority_id, approval_id)

    def _inspect_locked(self, claim, uncertain, authority_id, approval_id):
        if _present(uncertain):
            return RegistryReport("uncertain", None, None, ("uncertain",))
        db = _connect(self._root)
        try:
            row = db.execute("SELECT campaign,envelope,state FROM approvals WHERE authority=? AND approval_id=?", (authority_id, approval_id)).fetchone()
            history = tuple(r[0] for r in db.execute("SELECT state FROM history WHERE authority=? AND approval_id=? ORDER BY sequence", (authority_id, approval_id)))
        finally:
            _close(db)
        if row is None:
            return RegistryReport("uncertain" if _present(claim) else "absent", None, None, history)
        v.require(claim.is_file() and not claim.is_symlink())
        return RegistryReport(row[2], row[0], row[1], history)

    def record_outcome(self, *, authority_id, approval_id, campaign_id, envelope_sha256, outcome):
        try:
            claim, _ = self._paths(authority_id, approval_id)
        except Exception:
            deny(Rejected)
        with _approval_lock(claim):
            return self._record_outcome_locked(authority_id=authority_id, approval_id=approval_id,
                campaign_id=campaign_id, envelope_sha256=envelope_sha256, outcome=outcome)

    def _record_outcome_locked(self, *, authority_id, approval_id, campaign_id, envelope_sha256, outcome):
        """Record one declared terminal outcome. No operation or reconciliation is performed."""
        db = None
        uncertain = None
        commit_status = "not_attempted"
        try:
            v.identifier(campaign_id)
            v.digest(envelope_sha256)
            v.require(type(outcome) is str and outcome in v.OUTCOMES)
            claim, uncertain = self._paths(authority_id, approval_id)
            v.require(claim.is_file() and not _present(uncertain))
            db = _connect(self._root)
            db.execute("BEGIN IMMEDIATE")
            v.require(not _present(uncertain))
            row = db.execute("SELECT state,campaign,envelope FROM approvals WHERE authority=? AND approval_id=?", (authority_id, approval_id)).fetchone()
            v.require(row == ("consumed", campaign_id, envelope_sha256))
            if outcome == "uncertain":
                self._quarantine(uncertain)
            db.execute("UPDATE approvals SET state=? WHERE authority=? AND approval_id=? AND state='consumed'", (outcome, authority_id, approval_id))
            db.execute("INSERT INTO history(authority,approval_id,state) VALUES (?,?,?)", (authority_id, approval_id, outcome))
            commit_status = "uncertain"
            db.commit()
            commit_status = "confirmed"
        except Rejected:
            deny(Rejected)
        except Exception:
            if uncertain is not None:
                try:
                    self._quarantine(uncertain)
                except Exception:
                    pass
            _uncertain()
        finally:
            _close(db, commit_status=commit_status)
        return RegistryReport(outcome, campaign_id, envelope_sha256, ("consumed", outcome))
