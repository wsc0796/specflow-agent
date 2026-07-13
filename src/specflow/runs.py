"""Project-bound HTTP lifecycle for controlled mock workflow runs."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from specflow.db import Database, Project, ReviewDecision, WorkflowRun
from specflow.policy import DEFAULT_POLICY, RunStatus
from specflow.runner_multi import run_multi_agent

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])
_MAX_ARTIFACT_FILES = 32
_INTERRUPTED_ERROR_CODE = "INTERRUPTED"
_REVIEWABLE_RUN_STATES = frozenset({RunStatus.COMPLETED, RunStatus.COMPLETED_DEGRADED})


class RunCreate(BaseModel):
    project_id: str = Field(min_length=1, max_length=36, pattern=r"\S")
    requirement: str = Field(min_length=1, max_length=4000, pattern=r"\S")
    mock: Literal[True] = True


class RunRead(BaseModel):
    id: str
    project_id: str
    mode: str
    status: str
    result_status: str | None
    requirement_hash: str | None
    repository_alias: str | None
    policy_hash: str | None
    error_code: str | None
    started_at: datetime
    finished_at: datetime | None
    artifact_available: bool


class RunArtifactsRead(BaseModel):
    run_id: str
    files: list[str]


class ReviewDecisionCreate(BaseModel):
    decision: Literal["accepted", "needs_changes"]
    reviewer_label: str = Field(min_length=1, max_length=100, pattern=r"\S")
    rationale: str = Field(min_length=1, max_length=2000, pattern=r"\S")


class ReviewDecisionRead(BaseModel):
    id: int
    decision: str
    reviewer_label: str
    rationale: str
    created_at: datetime


class ReviewPackageRead(BaseModel):
    run: RunRead
    artifact_files: list[str]
    decisions: list[ReviewDecisionRead]


class ReviewUnavailableError(ValueError):
    """The Run cannot safely be presented for or receive a review decision."""


class RunRepository:
    def get(self, session: Session, run_id: str) -> WorkflowRun | None:
        return session.get(WorkflowRun, run_id)

    def add(self, session: Session, run: WorkflowRun) -> WorkflowRun:
        session.add(run)
        session.flush()
        return run

    def decisions_for_run(self, session: Session, run_id: str) -> list[ReviewDecision]:
        statement = (
            select(ReviewDecision)
            .where(ReviewDecision.run_id == run_id)
            .order_by(ReviewDecision.id)
        )
        return list(session.scalars(statement))

    def add_decision(
        self, session: Session, run: WorkflowRun, payload: ReviewDecisionCreate
    ) -> ReviewDecision:
        decision = ReviewDecision(
            run_id=run.id,
            decision=payload.decision,
            reviewer_label=payload.reviewer_label,
            rationale=payload.rationale,
        )
        session.add(decision)
        session.flush()
        return decision


class RunService:
    def __init__(self, repository: RunRepository, artifact_root: Path) -> None:
        self.repository = repository
        self.artifact_root = artifact_root.resolve()

    def create(self, session: Session, payload: RunCreate) -> WorkflowRun:
        project = session.get(Project, payload.project_id)
        if project is None:
            raise LookupError("project not found")

        run = self.repository.add(
            session,
            WorkflowRun(
                project_id=project.id,
                workflow_type="multi-agent",
                current_state=RunStatus.CREATED,
                state_payload={"mock": True},
                requirement_hash=sha256(payload.requirement.encode("utf-8")).hexdigest(),
                repository_alias=project.name,
                policy_hash=DEFAULT_POLICY.policy_hash(),
            ),
        )
        session.commit()

        run.current_state = RunStatus.RUNNING
        run.version += 1
        session.commit()

        output = self.artifact_root / run.id
        try:
            exit_code = run_multi_agent(
                repo=Path(project.repository_path),
                requirement=payload.requirement,
                output=output,
                mock=True,
            )
        except Exception:
            exit_code = -1

        run.current_state, run.result_status, run.error_code = _outcome_from_exit_code(exit_code)
        run.artifact_directory = self._artifact_directory(output)
        run.finished_at = datetime.now(UTC)
        run.version += 1
        session.commit()
        return run

    def get(self, session: Session, run_id: str) -> WorkflowRun:
        run = self.repository.get(session, run_id)
        if run is None:
            raise LookupError("run not found")
        return run

    def artifact_files(self, run: WorkflowRun) -> list[str]:
        if not run.artifact_directory:
            raise FileNotFoundError("artifacts not found")
        directory = (self.artifact_root / run.artifact_directory).resolve()
        if not directory.is_relative_to(self.artifact_root) or not directory.is_dir():
            raise FileNotFoundError("artifacts not found")
        files = [
            path.name
            for path in sorted(directory.iterdir())
            if path.is_file() and not path.is_symlink()
        ][:_MAX_ARTIFACT_FILES]
        if not files:
            raise FileNotFoundError("artifacts not found")
        return files

    def review_package(
        self, session: Session, run_id: str
    ) -> tuple[WorkflowRun, list[str], list[ReviewDecision]]:
        run = self.get(session, run_id)
        files = self._reviewable_artifact_files(run)
        return run, files, self.repository.decisions_for_run(session, run.id)

    def record_decision(
        self, session: Session, run_id: str, payload: ReviewDecisionCreate
    ) -> ReviewDecision:
        run = self.get(session, run_id)
        self._reviewable_artifact_files(run)
        decision = self.repository.add_decision(session, run, payload)
        session.commit()
        return decision

    def _reviewable_artifact_files(self, run: WorkflowRun) -> list[str]:
        if run.current_state not in _REVIEWABLE_RUN_STATES:
            raise ReviewUnavailableError("run is not reviewable")
        try:
            return self.artifact_files(run)
        except FileNotFoundError as error:
            raise ReviewUnavailableError("review artifacts are unavailable") from error

    def _artifact_directory(self, output: Path) -> str | None:
        if not output.is_dir():
            return None
        directories = [path for path in output.glob("run-multi-*") if path.is_dir()]
        if len(directories) != 1:
            return None
        candidate = directories[0].resolve()
        if not candidate.is_relative_to(self.artifact_root):
            return None
        return candidate.relative_to(self.artifact_root).as_posix()


def recover_interrupted_runs(database: Database) -> int:
    """Resolve runs left active by a previous single-process interruption.

    This does not retry or resume work: after a process restart, the synchronous
    mock executor that owned a durable ``running`` row no longer exists.
    """
    with database.engine.begin() as connection:
        result = connection.execute(
            update(WorkflowRun)
            .where(WorkflowRun.current_state == RunStatus.RUNNING)
            .values(
                current_state=RunStatus.FAILED_RUNTIME,
                result_status=RunStatus.FAILED_RUNTIME,
                error_code=_INTERRUPTED_ERROR_CODE,
                finished_at=datetime.now(UTC),
                version=func.coalesce(WorkflowRun.version, 0) + 1,
            )
        )
    return result.rowcount or 0


def _outcome_from_exit_code(exit_code: int) -> tuple[str, str, str | None]:
    if exit_code == 0:
        return RunStatus.COMPLETED, RunStatus.COMPLETED, None
    if exit_code == 4:
        return RunStatus.COMPLETED_DEGRADED, RunStatus.COMPLETED_DEGRADED, None
    if exit_code == 2:
        return RunStatus.FAILED_SECURITY, RunStatus.FAILED_SECURITY, "REPOSITORY_UNAVAILABLE"
    return RunStatus.FAILED_RUNTIME, RunStatus.FAILED_RUNTIME, "RUNNER_FAILED"


def get_session(request: Request) -> Generator[Session, None, None]:
    yield from request.app.state.database.sessions()


SessionDependency = Annotated[Session, Depends(get_session)]


def _service(request: Request) -> RunService:
    return RunService(RunRepository(), request.app.state.artifact_root)


@router.post("", response_model=RunRead, status_code=status.HTTP_201_CREATED)
def create_run(payload: RunCreate, request: Request, session: SessionDependency) -> RunRead:
    try:
        return _to_read(_service(request).create(session, payload))
    except LookupError as error:
        raise HTTPException(404, "Project not found.") from error


@router.get("/{run_id}/review-package", response_model=ReviewPackageRead)
def get_review_package(
    run_id: str, request: Request, session: SessionDependency
) -> ReviewPackageRead:
    service = _service(request)
    try:
        run, files, decisions = service.review_package(session, run_id)
        return ReviewPackageRead(
            run=_to_read(run),
            artifact_files=files,
            decisions=[_to_decision_read(decision) for decision in decisions],
        )
    except LookupError as error:
        raise HTTPException(404, "Run not found.") from error
    except ReviewUnavailableError as error:
        raise HTTPException(409, "Run is not ready for review.") from error


@router.post(
    "/{run_id}/review-decisions",
    response_model=ReviewDecisionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_review_decision(
    run_id: str,
    payload: ReviewDecisionCreate,
    request: Request,
    session: SessionDependency,
) -> ReviewDecisionRead:
    try:
        return _to_decision_read(_service(request).record_decision(session, run_id, payload))
    except LookupError as error:
        raise HTTPException(404, "Run not found.") from error
    except ReviewUnavailableError as error:
        raise HTTPException(409, "Run is not ready for review.") from error


@router.get("/{run_id}", response_model=RunRead)
def get_run(run_id: str, request: Request, session: SessionDependency) -> RunRead:
    try:
        return _to_read(_service(request).get(session, run_id))
    except LookupError as error:
        raise HTTPException(404, "Run not found.") from error


@router.get("/{run_id}/artifacts", response_model=RunArtifactsRead)
def get_run_artifacts(
    run_id: str, request: Request, session: SessionDependency
) -> RunArtifactsRead:
    service = _service(request)
    try:
        run = service.get(session, run_id)
        return RunArtifactsRead(run_id=run.id, files=service.artifact_files(run))
    except LookupError as error:
        raise HTTPException(404, "Run not found.") from error
    except FileNotFoundError as error:
        raise HTTPException(404, "Artifacts not found.") from error


def _to_read(run: WorkflowRun) -> RunRead:
    return RunRead(
        id=run.id,
        project_id=run.project_id,
        mode=run.workflow_type,
        status=run.current_state,
        result_status=run.result_status,
        requirement_hash=run.requirement_hash,
        repository_alias=run.repository_alias,
        policy_hash=run.policy_hash,
        error_code=run.error_code,
        started_at=run.started_at,
        finished_at=run.finished_at,
        artifact_available=run.artifact_directory is not None,
    )


def _to_decision_read(decision: ReviewDecision) -> ReviewDecisionRead:
    return ReviewDecisionRead(
        id=decision.id,
        decision=decision.decision,
        reviewer_label=decision.reviewer_label,
        rationale=decision.rationale,
        created_at=decision.created_at,
    )
