"""New tables coexist with old application data and enforce real DB constraints."""

import json
import sqlite3
from contextlib import closing

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from specflow.contract_review import store as store_module
from specflow.contract_review.common import ReviewError
from specflow.contract_review.instance_lock import InstanceLock
from specflow.contract_review.schemas import CreateReview
from specflow.contract_review.service import ReviewService
from specflow.contract_review.sources import GitSnapshotReader
from specflow.contract_review.store import DDL, SCHEMA_CHECKSUM, ReviewStore
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
                == 3
            )
    finally:
        db.engine.dispose()


@pytest.mark.parametrize("fail_upgrade", [False, True])
def test_v2_to_v3_preserves_queued_data_steps_and_rolls_back_ddl(
    tmp_path, git_repo, test_profile, monkeypatch, fail_upgrade
):
    root, _, body = git_repo
    db = Database(f"sqlite:///{(tmp_path / 'v2.sqlite').as_posix()}")
    try:
        db.create_schema()
        with db.factory() as session:
            session.add(
                Project(id=body["project_id"], name="V2 project", repository_path=str(root))
            )
            session.commit()
        store = ReviewStore(db)
        with monkeypatch.context() as previous:
            previous.setattr(store_module, "MIGRATIONS", store_module.MIGRATIONS[:2])
            store.migrate()
        domain = ReviewService(
            store, GitSnapshotReader(lambda path: path), {test_profile["profile_id"]: test_profile}
        )
        _, accepted = domain.create(CreateReview.model_validate(body), "before-v3")
        original = domain.get(accepted["review_id"])
        with store.transaction() as conn:
            store.execute(
                conn,
                "INSERT INTO contract_review_steps VALUES ('old-step',:job,1,'analysis','logical')",
                job=accepted["job_id"],
            )
            previous_versions = conn.exec_driver_sql(
                "SELECT version,checksum FROM contract_review_schema_migrations ORDER BY version"
            ).all()
        if fail_upgrade:
            monkeypatch.setattr(
                store_module,
                "MIGRATIONS",
                (
                    *store_module.MIGRATIONS[:2],
                    (3, (*store_module.DYNAMIC_DDL, "INVALID MIGRATION STATEMENT")),
                ),
            )
            with pytest.raises(ReviewError):
                store.migrate()
        else:
            store.migrate()
            backup = store.migration_backup_path
            store.migrate()
            assert store.migration_backup_path == backup
        assert domain.get(accepted["review_id"])["input_hash"] == original["input_hash"]
        assert domain.get(accepted["review_id"])["status"] == "queued"
        with store.read() as conn:
            assert (
                conn.exec_driver_sql(
                    "SELECT version,checksum FROM contract_review_schema_migrations "
                    "WHERE version<=2 ORDER BY version"
                ).all()
                == previous_versions
            )
            columns = {
                row[1] for row in conn.exec_driver_sql("PRAGMA table_info(contract_review_steps)")
            }
            assert ("body" in columns) is not fail_upgrade
            if not fail_upgrade:
                assert (
                    conn.exec_driver_sql(
                        "SELECT body FROM contract_review_steps WHERE id='old-step'"
                    ).scalar_one()
                    == "{}"
                )
            for table in ("contract_review_actions", "contract_review_child_tasks"):
                assert (
                    bool(
                        store.row(
                            conn, "SELECT name FROM sqlite_master WHERE name=:name", name=table
                        )
                    )
                    is not fail_upgrade
                )
            assert conn.exec_driver_sql(
                "SELECT max(version) FROM contract_review_schema_migrations"
            ).scalar_one() == (2 if fail_upgrade else 3)
        with closing(sqlite3.connect(store.migration_backup_path)) as backup:
            assert backup.execute(
                "SELECT max(version) FROM contract_review_schema_migrations"
            ).fetchone() == (2,)
            assert backup.execute("SELECT id FROM contract_review_inputs").fetchone() == (
                accepted["input_revision_id"],
            )
    finally:
        db.engine.dispose()


def test_future_schema_rejected_without_rewriting_it(review_client):
    _, domain, _ = review_client
    with domain.store.transaction() as conn:
        conn.exec_driver_sql(
            "UPDATE contract_review_schema_migrations SET version=99 WHERE version=2"
        )
    with pytest.raises(ReviewError):
        domain.store.migrate()
    with domain.store.read() as conn:
        assert (
            conn.exec_driver_sql(
                "SELECT max(version) FROM contract_review_schema_migrations"
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


@pytest.mark.parametrize("fail_upgrade", [False, True])
def test_v1_upgrade_preserves_queued_input_and_rolls_back_partial_v2(
    tmp_path, git_repo, test_profile, monkeypatch, fail_upgrade
):
    assert SCHEMA_CHECKSUM == "90c77e6473bdf6bd2d0b2526199421fe2391e8a4dfefee5f6650b2328f48f061"
    root, _, body = git_repo
    db = Database(f"sqlite:///{(tmp_path / 'v1.sqlite').as_posix()}")
    try:
        db.create_schema()
        with db.factory() as session:
            session.add(
                Project(id=body["project_id"], name="Before upgrade", repository_path=str(root))
            )
            session.commit()
        store = ReviewStore(db)
        with store.transaction() as conn:
            for statement in DDL:
                conn.exec_driver_sql(statement)
            conn.execute(
                text("INSERT INTO contract_review_schema_migrations VALUES (1,:hash,'2026-10-30')"),
                {"hash": SCHEMA_CHECKSUM},
            )
        domain = ReviewService(
            store, GitSnapshotReader(lambda path: path), {test_profile["profile_id"]: test_profile}
        )
        _, accepted = domain.create(CreateReview.model_validate(body), "before-upgrade")
        original = domain.get(accepted["review_id"])
        if fail_upgrade:
            monkeypatch.setattr(
                store_module,
                "MIGRATIONS",
                (
                    (1, DDL),
                    (2, (*store_module.EVIDENCE_DDL, "INVALID MIGRATION STATEMENT")),
                ),
            )
            with pytest.raises(ReviewError):
                store.migrate()
        else:
            store.migrate()
            store.migrate()
        assert domain.get(accepted["review_id"])["input_hash"] == original["input_hash"]
        with store.read() as conn:
            assert conn.exec_driver_sql(
                "SELECT max(version) FROM contract_review_schema_migrations"
            ).scalar_one() == (1 if fail_upgrade else 3)
            found = conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE name='contract_review_verification_evidence'"
            ).first()
            assert bool(found) is not fail_upgrade
        with closing(sqlite3.connect(store.migration_backup_path)) as backup:
            assert backup.execute(
                "SELECT max(version) FROM contract_review_schema_migrations"
            ).fetchone() == (1,)
            assert backup.execute("SELECT id FROM contract_review_inputs").fetchone() == (
                accepted["input_revision_id"],
            )
        db.create_schema()
        with db.factory() as session:
            assert session.get(Project, body["project_id"]).name == "Before upgrade"
    finally:
        db.engine.dispose()
