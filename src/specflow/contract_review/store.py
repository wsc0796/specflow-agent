"""Versioned additive SQLite records with short, explicit write transactions."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from specflow.contract_review.common import ReviewError, canonical, digest, identity, now

DDL = (
    "CREATE TABLE contract_review_schema_migrations "
    "(version INTEGER PRIMARY KEY, checksum TEXT NOT NULL, applied_at TEXT NOT NULL)",
    "CREATE TABLE contract_reviews (id TEXT PRIMARY KEY, project_id TEXT NOT NULL "
    "REFERENCES projects(id), status TEXT NOT NULL, version INTEGER NOT NULL, "
    "current_input_id TEXT, current_report_id TEXT, active_job_id TEXT, "
    "event_seq INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)",
    "CREATE TABLE contract_review_snapshots (id TEXT PRIMARY KEY, project_id TEXT NOT NULL "
    "REFERENCES projects(id), commit_sha TEXT NOT NULL, manifest TEXT NOT NULL, "
    "byte_count INTEGER NOT NULL CHECK(byte_count>=0))",
    "CREATE TABLE contract_review_source_blobs (id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL "
    "REFERENCES contract_review_snapshots(id), path TEXT NOT NULL, roles TEXT NOT NULL, "
    "raw_bytes BLOB NOT NULL, body_hash TEXT NOT NULL, UNIQUE(snapshot_id,path))",
    "CREATE TABLE contract_review_inputs (id TEXT PRIMARY KEY, review_id TEXT NOT NULL "
    "REFERENCES contract_reviews(id), revision_no INTEGER NOT NULL, snapshot_id TEXT NOT NULL "
    "REFERENCES contract_review_snapshots(id), body TEXT NOT NULL, input_hash TEXT NOT NULL, "
    "created_at TEXT NOT NULL, UNIQUE(review_id,revision_no))",
    "CREATE TABLE contract_review_jobs (id TEXT PRIMARY KEY, review_id TEXT NOT NULL "
    "REFERENCES contract_reviews(id), input_id TEXT NOT NULL "
    "REFERENCES contract_review_inputs(id), "
    "attempt_no INTEGER NOT NULL, status TEXT NOT NULL CHECK(status IN "
    "('queued','running','completed','failed','interrupted')), owner_boot_id TEXT, "
    "attempt_token TEXT, started_at TEXT, deadline TEXT, finished_at TEXT, "
    "body TEXT NOT NULL, error_code TEXT, created_at TEXT NOT NULL, "
    "record_bytes INTEGER NOT NULL DEFAULT 0, UNIQUE(review_id,attempt_no))",
    "CREATE UNIQUE INDEX contract_review_one_active_job ON contract_review_jobs(review_id) "
    "WHERE status IN ('queued','running')",
    "CREATE TABLE contract_review_reports (id TEXT PRIMARY KEY, review_id TEXT NOT NULL "
    "REFERENCES contract_reviews(id), input_id TEXT NOT NULL "
    "REFERENCES contract_review_inputs(id), "
    "job_id TEXT NOT NULL UNIQUE REFERENCES contract_review_jobs(id), "
    "revision_no INTEGER NOT NULL, "
    "body TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(review_id,revision_no))",
    "CREATE TABLE contract_review_budget_accounts (review_id TEXT PRIMARY KEY "
    "REFERENCES contract_reviews(id), body TEXT NOT NULL, version INTEGER NOT NULL)",
    "CREATE TABLE contract_review_events (id TEXT PRIMARY KEY, review_id TEXT NOT NULL "
    "REFERENCES contract_reviews(id), event_seq INTEGER NOT NULL, input_id TEXT, job_id TEXT, "
    "event_type TEXT NOT NULL, body TEXT NOT NULL, payload TEXT NOT NULL, "
    "payload_hash TEXT NOT NULL, "
    "created_at TEXT NOT NULL, UNIQUE(review_id,event_seq))",
    "CREATE INDEX contract_review_events_by_job "
    "ON contract_review_events(review_id,job_id,event_seq)",
    "CREATE TABLE contract_review_idempotency (scope TEXT NOT NULL, key_digest TEXT NOT NULL, "
    "payload_hash TEXT NOT NULL, status_code INTEGER NOT NULL, response TEXT NOT NULL, "
    "created_at TEXT NOT NULL, PRIMARY KEY(scope,key_digest))",
    "CREATE TABLE contract_review_capacity (id INTEGER PRIMARY KEY CHECK(id=1), "
    "snapshot_bytes INTEGER NOT NULL, record_bytes INTEGER NOT NULL)",
    "INSERT INTO contract_review_capacity VALUES (1,0,0)",
    "CREATE TABLE contract_review_steps (id TEXT PRIMARY KEY, job_id TEXT NOT NULL "
    "REFERENCES contract_review_jobs(id), step_seq INTEGER NOT NULL, role TEXT NOT NULL, "
    "logical_call_id TEXT NOT NULL, UNIQUE(job_id,step_seq))",
    "CREATE TABLE contract_review_calls (id TEXT PRIMARY KEY, job_id TEXT NOT NULL "
    "REFERENCES contract_review_jobs(id), step_id TEXT NOT NULL REFERENCES "
    "contract_review_steps(id), "
    "physical_retry_no INTEGER NOT NULL, status TEXT NOT NULL, body TEXT NOT NULL, "
    "version INTEGER NOT NULL, UNIQUE(step_id,physical_retry_no))",
    "CREATE TABLE contract_review_budget_entries (id TEXT PRIMARY KEY, review_id TEXT NOT NULL "
    "REFERENCES contract_reviews(id), job_id TEXT NOT NULL REFERENCES contract_review_jobs(id), "
    "call_id TEXT REFERENCES contract_review_calls(id), body TEXT NOT NULL)",
    "CREATE TABLE contract_review_runtime (id INTEGER PRIMARY KEY CHECK(id=1), "
    "owner_boot_id TEXT, slot_call_id TEXT REFERENCES contract_review_calls(id), "
    "slot_execution_instance_id TEXT)",
    "INSERT INTO contract_review_runtime VALUES (1,NULL,NULL,NULL)",
)
SCHEMA_CHECKSUM = digest(DDL)


class ReviewStore:
    def __init__(self, database, *, snapshot_capacity=1024**3, record_capacity=1024**3):
        self.database = database
        self.snapshot_capacity = snapshot_capacity
        self.record_capacity = record_capacity
        self.migration_backup_path = None

    @contextmanager
    def transaction(self):
        with self.database.engine.connect() as conn:
            try:
                conn.exec_driver_sql("BEGIN IMMEDIATE")
                yield conn
                conn.commit()
            except OperationalError as error:
                conn.rollback()
                code = (
                    "DATABASE_BUSY" if "locked" in str(error).lower() else "DEPENDENCY_UNAVAILABLE"
                )
                raise ReviewError(code, "数据库暂时无法可靠提交。", 503) from error
            except BaseException:
                conn.rollback()
                raise

    @contextmanager
    def read(self):
        with self.database.engine.connect() as conn:
            conn.exec_driver_sql("BEGIN")
            try:
                yield conn
            finally:
                conn.rollback()

    def migrate(self):
        with self.transaction() as conn:
            exists = conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='contract_review_schema_migrations'"
            ).first()
            if exists:
                versions = conn.exec_driver_sql(
                    "SELECT version,checksum FROM contract_review_schema_migrations "
                    "ORDER BY version"
                ).all()
                if versions != [(1, SCHEMA_CHECKSUM)]:
                    raise ReviewError("DEPENDENCY_UNAVAILABLE", "审查数据版本不兼容。", 503)
                return
            # The write reservation prevents concurrent DB changes while a
            # separate read connection takes a consistent, pre-upgrade backup.
            path = Path(self.database.engine.url.database).resolve()
            backup = path.with_name(
                path.name + ".before-contract-review-v1-" + identity("b") + ".sqlite3"
            )
            with self.database.engine.connect() as source:
                destination = sqlite3.connect(backup)
                try:
                    source.connection.driver_connection.backup(destination)
                finally:
                    destination.close()
            self.migration_backup_path = backup
            for statement in DDL:
                conn.exec_driver_sql(statement)
            conn.execute(
                text("INSERT INTO contract_review_schema_migrations VALUES (1,:checksum,:applied)"),
                {"checksum": SCHEMA_CHECKSUM, "applied": now()},
            )

    @staticmethod
    def row(conn, statement: str, **params):
        return conn.execute(text(statement), params).mappings().first()

    @staticmethod
    def execute(conn, statement: str, **params):
        return conn.execute(text(statement), params)

    def reserve_records(self, conn, byte_count: int, job_id=None):
        result = self.execute(
            conn,
            "UPDATE contract_review_capacity SET record_bytes=record_bytes+:size "
            "WHERE id=1 AND record_bytes+:size<=:capacity",
            size=byte_count,
            capacity=self.record_capacity,
        )
        if result.rowcount != 1:
            raise ReviewError("STORAGE_CAPACITY_EXCEEDED", "必要记录容量不足。", 503)
        if job_id is not None:
            result = self.execute(
                conn,
                "UPDATE contract_review_jobs SET record_bytes=record_bytes+:size "
                "WHERE id=:job AND record_bytes+:size<=:capacity",
                size=byte_count,
                job=job_id,
                capacity=8 * 1024**2,
            )
            if result.rowcount != 1:
                raise ReviewError("STORAGE_CAPACITY_EXCEEDED", "本次作业记录容量不足。", 503)

    def event(self, conn, review_id, input_id, job_id, event_type, payload, **links):
        self.execute(
            conn, "UPDATE contract_reviews SET event_seq=event_seq+1 WHERE id=:id", id=review_id
        )
        row = self.row(conn, "SELECT event_seq FROM contract_reviews WHERE id=:id", id=review_id)
        event_id, timestamp = identity("evt"), now()
        body = {
            "event_id": event_id,
            "review_id": review_id,
            "event_seq": row["event_seq"],
            "input_revision_id": input_id,
            "job_id": job_id,
            "event_type": event_type,
            "occurred_at": timestamp,
            "recorded_at": timestamp,
            "caused_by_event_id": None,
            "target_refs": [],
            "payload_ref": event_id,
            "payload_hash": digest(payload),
            "evidence_integrity": "complete",
            **links,
        }
        body_text, payload_text = canonical(body), canonical(payload)
        self.reserve_records(
            conn, len(body_text.encode("utf-8")) + len(payload_text.encode("utf-8")), job_id
        )
        self.execute(
            conn,
            "INSERT INTO contract_review_events VALUES "
            "(:id,:review,:seq,:input,:job,:type,:body,:payload,:hash,:created)",
            id=event_id,
            review=review_id,
            seq=row["event_seq"],
            input=input_id,
            job=job_id,
            type=event_type,
            body=body_text,
            payload=payload_text,
            hash=body["payload_hash"],
            created=timestamp,
        )
        return body
