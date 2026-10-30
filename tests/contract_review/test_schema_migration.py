"""New tables coexist with old application data and enforce real DB constraints."""

import json
import sqlite3
from contextlib import closing

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from specflow.contract_review.common import ReviewError
from specflow.contract_review.instance_lock import InstanceLock
from specflow.contract_review.store import ReviewStore
from specflow.db import Database, Project


def test_migration_is_repeatable_and_legacy_reader_preserves_new_data(tmp_path):
    path = tmp_path / "migration.sqlite"
    db = Database(f"sqlite:///{path.as_posix()}")
    try:
        db.create_schema()
        with db.factory() as session:
            session.add(Project(id="p", name="Before upgrade", repository_path=str(tmp_path)))
            session.commit()
        store = ReviewStore(db)
        store.migrate()
        backup = store.migration_backup_path
        assert backup.is_file()
        with closing(sqlite3.connect(backup)) as copy:
            assert copy.execute("SELECT name FROM projects WHERE id='p'").fetchone() == (
                "Before upgrade",
            )
            assert (
                copy.execute(
                    "SELECT name FROM sqlite_master WHERE name='contract_reviews'"
                ).fetchone()
                is None
            )
        store.migrate()
        assert store.migration_backup_path == backup
        # Same legacy schema initializer ignores the new additive schema.
        db.create_schema()
        with db.factory() as session:
            assert session.get(Project, "p").name == "Before upgrade"
        with store.read() as conn:
            assert (
                conn.exec_driver_sql(
                    "SELECT count(*) FROM contract_review_schema_migrations"
                ).scalar_one()
                == 1
            )
    finally:
        db.engine.dispose()


def test_future_schema_rejected_without_rewriting_it(review_client):
    _, domain, _ = review_client
    with domain.store.transaction() as conn:
        conn.exec_driver_sql("UPDATE contract_review_schema_migrations SET version=99")
    with pytest.raises(ReviewError):
        domain.store.migrate()
    with domain.store.read() as conn:
        assert (
            conn.exec_driver_sql(
                "SELECT version FROM contract_review_schema_migrations"
            ).scalar_one()
            == 99
        )


def test_database_enforces_one_active_job_and_compare_and_swap(review_client):
    client, domain, body = review_client
    result = client.post(
        "/api/v1/contract-reviews", json=body, headers={"Idempotency-Key": "one"}
    ).json()
    with pytest.raises(IntegrityError), domain.store.transaction() as conn:
        conn.execute(
            text(
                "INSERT INTO contract_review_jobs "
                "(id,review_id,input_id,attempt_no,status,body,created_at) "
                "SELECT 'other',review_id,input_id,2,'queued',body,created_at "
                "FROM contract_review_jobs"
            )
        )
    with domain.store.transaction() as conn:
        assert (
            domain.store.execute(
                conn,
                "UPDATE contract_reviews SET version=version+1 WHERE id=:id AND version=1",
                id=result["review_id"],
            ).rowcount
            == 1
        )
        assert (
            domain.store.execute(
                conn,
                "UPDATE contract_reviews SET version=version+1 WHERE id=:id AND version=1",
                id=result["review_id"],
            ).rowcount
            == 0
        )
    # Replay precedes mutable version/state and returns its original response.
    assert (
        client.post(
            "/api/v1/contract-reviews", json=body, headers={"Idempotency-Key": "one"}
        ).json()
        == result
    )


def test_new_connection_can_reconstruct_input_after_process_local_objects_are_discarded(
    review_client,
):
    client, domain, body = review_client
    result = client.post(
        "/api/v1/contract-reviews", json=body, headers={"Idempotency-Key": "one"}
    ).json()
    fresh_db = Database(str(domain.store.database.engine.url))
    try:
        fresh_store = ReviewStore(fresh_db)
        with fresh_store.read() as conn:
            row = fresh_store.row(
                conn,
                "SELECT body FROM contract_review_inputs WHERE id=:id",
                id=result["input_revision_id"],
            )
            assert json.loads(row["body"])["original_request"] == body
            blobs = conn.exec_driver_sql(
                "SELECT raw_bytes,body_hash FROM contract_review_source_blobs"
            ).all()
            assert len(blobs) == 4
    finally:
        fresh_db.engine.dispose()


def test_instance_lock_cannot_be_acquired_twice_until_released(tmp_path):
    path = str(tmp_path / "locked.sqlite")
    first, second = InstanceLock(path), InstanceLock(path)
    first.acquire()
    try:
        with pytest.raises(RuntimeError):
            second.acquire()
    finally:
        first.release()
    second.acquire()
    second.release()
