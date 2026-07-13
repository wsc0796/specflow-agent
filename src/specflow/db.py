"""SQLite persistence for T-002."""

from collections.abc import Generator
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    event,
    func,
    inspect,
    text,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200))
    repository_path: Mapped[str] = mapped_column(String(1024), unique=True)
    latest_scan_id: Mapped[str | None] = mapped_column(String(36))
    context_version: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="registered")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    scans: Mapped[list["ProjectScan"]] = relationship(back_populates="project")
    runs: Mapped[list["WorkflowRun"]] = relationship(back_populates="project")


class ProjectScan(Base):
    __tablename__ = "project_scans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    source_hash: Mapped[str | None] = mapped_column(String(128))
    tech_stack: Mapped[dict | None] = mapped_column(JSON)
    directory_summary: Mapped[dict | None] = mapped_column(JSON)
    symbol_index: Mapped[dict | None] = mapped_column(JSON)
    scan_result: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    project: Mapped[Project] = relationship(back_populates="scans")


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    requirement_id: Mapped[str | None] = mapped_column(String(36))
    workflow_type: Mapped[str] = mapped_column(String(64))
    current_state: Mapped[str] = mapped_column(String(64), default="created")
    state_payload: Mapped[dict | None] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, default=1)
    result_status: Mapped[str | None] = mapped_column(String(32))
    requirement_hash: Mapped[str | None] = mapped_column(String(64))
    repository_alias: Mapped[str | None] = mapped_column(String(200))
    policy_hash: Mapped[str | None] = mapped_column(String(64))
    artifact_directory: Mapped[str | None] = mapped_column(String(512))
    error_code: Mapped[str | None] = mapped_column(String(128))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_error: Mapped[str | None] = mapped_column(Text)
    project: Mapped[Project] = relationship(back_populates="runs")
    review_decisions: Mapped[list["ReviewDecision"]] = relationship(back_populates="run")


class ReviewDecision(Base):
    """Append-only, unverified human feedback attached to a reviewable Run."""

    __tablename__ = "review_decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"))
    decision: Mapped[str] = mapped_column(String(32))
    reviewer_label: Mapped[str] = mapped_column(String(100))
    rationale: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    run: Mapped[WorkflowRun] = relationship(back_populates="review_decisions")


class Database:
    def __init__(self, url: str) -> None:
        self.engine = create_engine(url, connect_args={"check_same_thread": False})
        event.listen(
            self.engine,
            "connect",
            lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"),
        )
        self.factory = sessionmaker(self.engine, expire_on_commit=False)

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)
        self._add_workflow_run_metadata_columns()

    def _add_workflow_run_metadata_columns(self) -> None:
        """Reconcile additive T-056 fields for pre-existing SQLite databases.

        `create_all` deliberately does not alter existing tables.  This small,
        idempotent compatibility bridge adds only nullable metadata columns and
        avoids introducing a migration framework for the portfolio's SQLite
        single-process deployment scope.
        """
        if self.engine.dialect.name != "sqlite":
            return

        existing = {column["name"] for column in inspect(self.engine).get_columns("workflow_runs")}
        missing_columns = {
            "requirement_hash": "VARCHAR(64)",
            "repository_alias": "VARCHAR(200)",
            "policy_hash": "VARCHAR(64)",
            "artifact_directory": "VARCHAR(512)",
            "error_code": "VARCHAR(128)",
        }
        with self.engine.begin() as connection:
            for name, definition in missing_columns.items():
                if name not in existing:
                    connection.execute(
                        text(f"ALTER TABLE workflow_runs ADD COLUMN {name} {definition}")
                    )

    def sessions(self) -> Generator[Session, None, None]:
        session = self.factory()
        try:
            yield session
        finally:
            session.close()


def default_url() -> str:
    path = Path("data/specflow.db")
    path.parent.mkdir(exist_ok=True)
    return f"sqlite:///{path.as_posix()}"
