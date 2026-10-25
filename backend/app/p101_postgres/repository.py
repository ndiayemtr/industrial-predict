"""PostgreSQL statements, invoked only by an explicitly authorized service call."""

from sqlalchemy import insert, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.anomaly_detection.p101_canonical import instant_datetime
from app.p101_postgres.mapping import instant, validate_read
from app.p101_postgres.runtime import ContentConflict
from app.p101_postgres.tables import predictions, registry


def reservation_statement(target, prediction_id, created_at):
    return pg_insert(registry).values(
        idempotency_key=target.key.projection.sha256,
        key_canonical=target.key.projection.canonical_json, content_sha256=target.content.sha256,
        content_canonical=target.content.canonical_json, prediction_id=prediction_id,
        first_created_at=instant_datetime(instant(created_at)),
    ).on_conflict_do_nothing(index_elements=[registry.c.idempotency_key]).returning(registry.c.prediction_id)


class P101Repository:
    def __init__(self, session):
        self.session = session

    def lock_sources(self):
        return tuple(dict(row) for row in self.session.execute(text(
            "SELECT * FROM p101_pilot.lock_sources()"
        )).mappings())

    def next_id(self):
        return self.session.execute(text(
            "SELECT nextval(pg_get_serial_sequence('public.prediction_records','id'))"
        )).scalar_one()

    def clock(self):
        return self.session.execute(text("SELECT clock_timestamp()" )).scalar_one()

    def find(self, target):
        return self.session.execute(select(registry).where(
            registry.c.idempotency_key == target.key.projection.sha256
        )).mappings().one_or_none()

    def reserve(self, target, prediction_id, created_at):
        result = self.session.execute(reservation_statement(target, prediction_id, created_at)).scalar_one_or_none()
        if result is not None:
            return True, None
        # Separate statement: READ COMMITTED obtains a fresh snapshot after a conflict.
        row = self.find(target)
        if row is None:
            raise ContentConflict("Conflicting registry row not visible")
        return False, row

    def insert_prediction(self, row):
        values = dict(row)
        for key in ("predicted_at", "created_at"):
            values[key] = instant_datetime(values[key])
        self.session.execute(insert(predictions).values(**values))

    def existing(self, dossier, target, sources, ledger):
        if (ledger["idempotency_key"] != target.key.projection.sha256
                or ledger["key_canonical"] != target.key.projection.canonical_json
                or ledger["content_sha256"] != target.content.sha256
                or ledger["content_canonical"] != target.content.canonical_json):
            raise ContentConflict("Existing P101 content differs")
        row = dict(self.session.execute(select(predictions).where(
            predictions.c.id == ledger["prediction_id"])).mappings().one())
        for key in ("predicted_at", "created_at"):
            row[key] = instant(row[key])
        if instant(ledger["first_created_at"]) != row["created_at"]:
            raise ContentConflict("First-write timestamp differs")
        validate_read(dossier, target, sources, row)
        return row

    def check_constraints(self):
        self.session.execute(text(
            "SET CONSTRAINTS p101_pilot.p101_prediction_fk, "
            "p101_pilot.p101_registry_link, public.p101_prediction_link IMMEDIATE"
        ))
