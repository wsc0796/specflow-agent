"""v5 to v6 rollback/reentry preserves the existing formal-input bytes."""

import sqlite3
from contextlib import closing

import pytest

from specflow.contract_review import store as store_module
from specflow.contract_review.common import ReviewError
from specflow.contract_review.schemas import CreateReview
from specflow.contract_review.service import ReviewService
from specflow.contract_review.sources import GitSnapshotReader
from specflow.contract_review.store import ReviewStore
from specflow.db import Database, Project


@pytest.mark.parametrize("fail_upgrade", [False, True])
def test_v5_to_v6_preserves_old_checksums_input_and_backup(
    tmp_path, git_repo, test_profile, monkeypatch, fail_upgrade
):
    root, _, body = git_repo
    db = Database(f"sqlite:///{(tmp_path / 'upgrade.sqlite').as_posix()}")
    try:
        db.create_schema()
        with db.factory() as session:
            session.add(Project(id="project-test", name="Old", repository_path=str(root)))
            session.commit()
        store = ReviewStore(db)
        with monkeypatch.context() as old:
            old.setattr(store_module, "MIGRATIONS", store_module.MIGRATIONS[:5])
            store.migrate()
        service = ReviewService(
            store, GitSnapshotReader(lambda path: path), {test_profile["profile_id"]: test_profile}
        )
        _, accepted = service.create(CreateReview.model_validate(body), "before-v6")
        with store.read() as conn:
            original = conn.exec_driver_sql("SELECT body FROM contract_review_inputs").scalar_one()
            old_versions = conn.exec_driver_sql(
                "SELECT version,checksum FROM contract_review_schema_migrations ORDER BY version"
            ).all()
        if fail_upgrade:
            monkeypatch.setattr(
                store_module,
                "MIGRATIONS",
                (*store_module.MIGRATIONS[:5], (6, (*store_module.IMPACT_DDL, "INVALID SQL"))),
            )
            with pytest.raises(ReviewError):
                store.migrate()
        else:
            store.migrate()
            backup = store.migration_backup_path
            store.migrate()
            assert store.migration_backup_path == backup
        with store.read() as conn:
            assert (
                conn.exec_driver_sql("SELECT body FROM contract_review_inputs").scalar_one()
                == original
            )
            assert (
                conn.exec_driver_sql(
                    "SELECT version,checksum FROM contract_review_schema_migrations "
                    "WHERE version<=5 ORDER BY version"
                ).all()
                == old_versions
            )
            assert conn.exec_driver_sql(
                "SELECT max(version) FROM contract_review_schema_migrations"
            ).scalar_one() == (5 if fail_upgrade else 6)
            tables = {
                row[0]
                for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")
            }
            assert ("contract_impact_discoveries" in tables) is not fail_upgrade
        with closing(sqlite3.connect(store.migration_backup_path)) as backup:
            assert backup.execute(
                "SELECT max(version) FROM contract_review_schema_migrations"
            ).fetchone() == (5,)
            assert backup.execute("SELECT body FROM contract_review_inputs").fetchone() == (
                original,
            )
        assert service.get(accepted["review_id"])["status"] == "queued"
    finally:
        db.engine.dispose()
