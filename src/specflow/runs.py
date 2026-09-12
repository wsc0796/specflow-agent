"""Project-bound HTTP lifecycle for controlled mock workflow runs."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Generator
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from specflow.db import Database, Project, ReviewDecision, WorkflowRun
from specflow.policy import DEFAULT_POLICY, RunStatus, SpecFlowError
from specflow.runner_multi import run_multi_agent
from specflow.single_flight import (
    DEFAULT_COORDINATOR,
    RunResult,
    SingleFlightCoordinator,
    prepare_run,
)

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])
logger = logging.getLogger(__name__)
_MAX_ARTIFACT_FILES = 32
_INTERRUPTED_ERROR_CODE = "INTERRUPTED"
_REVIEWABLE_RUN_STATES = frozenset({RunStatus.COMPLETED, RunStatus.COMPLETED_DEGRADED})
_SAFE_RUNNER_ERROR_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}")


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
    single_flight: SingleFlightRead | None = None


class SingleFlightRead(BaseModel):
    role: Literal["owner", "follower"]
    owner_run_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9-]+$")


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
    def __init__(
        self,
        repository: RunRepository,
        artifact_root: Path,
        validate_repository_path: Callable[[str], Path],
        *,
        admit: Callable[[bool], Callable[[], None] | None] | None = None,
        coordinator: SingleFlightCoordinator | None = None,
    ) -> None:
        self.repository = repository
        self.artifact_root = artifact_root.resolve()
        self._validate_repository_path = validate_repository_path
        self._admit = admit
        self._coordinator = coordinator or DEFAULT_COORDINATOR

    def create(self, session: Session, payload: RunCreate) -> WorkflowRun:
        project = session.get(Project, payload.project_id)
        if project is None:
            raise LookupError("project not found")
        # Project records can predate an allowlist change, and a path can be
        # retargeted through a symlink after registration. Revalidate at the
        # execution boundary before any runner reads the repository.
        repository_path = self._validate_repository_path(project.repository_path)
        try:
            prepared = prepare_run(
                repo=repository_path,
                requirement=payload.requirement,
                mode="multi-agent",
                mock=True,
                provider="mock",
                model="mock-model",
                extra={"executors": {}},
            )
        except SpecFlowError as error:
            # An accepted invalid repository still gets its existing durable
            # failure identity. It never joins an in-flight execution.
            release = self._admit(True) if self._admit else None
            try:
                run = self._start_run(session, project, payload, str(uuid4()), None)
                code = "REPOSITORY_UNAVAILABLE" if not repository_path.is_dir() else error.code
                return self._finish_run(session, run, RunResult(2, error_code=code))
            finally:
                if release:
                    release()

        with self._coordinator.claim(prepared, str(uuid4()), self._admit) as flight:
            run_id = flight.metadata["owner_run_id"] if flight.owner else str(uuid4())
            run = self._start_run(session, project, payload, run_id, flight.metadata)
            try:
                if flight.owner:
                    output = self.artifact_root / run.id
                    try:
                        result = run_multi_agent(
                            repo=repository_path,
                            requirement=payload.requirement,
                            output=output,
                            mock=True,
                            _flight=flight,
                        )
                    except Exception:
                        logger.error("run %s failed with an unexpected exception", run.id)
                        result = RunResult(3, error_code="RUNNER_FAILED")
                    # Keep compatibility with integer-returning runner adapters.
                    if not isinstance(result, RunResult):
                        relative = self._artifact_directory(output)
                        result = RunResult(
                            result,
                            error_code=self._failed_error_code(output) if result == 3 else None,
                            artifact_directory=self.artifact_root / relative if relative else None,
                        )
                else:
                    result = flight.wait(DEFAULT_POLICY.max_wall_time_seconds)
                self._finish_run(session, run, result)
                if flight.owner:
                    flight.complete(result)
                return run
            except BaseException as error:
                if not isinstance(error, Exception):
                    self._finish_run(
                        session,
                        run,
                        RunResult(3, error_code="RUN_CANCELLED", result_status=RunStatus.CANCELLED),
                    )
                raise

    def _start_run(
        self,
        session: Session,
        project: Project,
        payload: RunCreate,
        run_id: str,
        metadata: dict[str, str] | None,
    ) -> WorkflowRun:
        run = self.repository.add(
            session,
            WorkflowRun(
                id=run_id,
                project_id=project.id,
                workflow_type="multi-agent",
                current_state=RunStatus.CREATED,
                state_payload={"mock": True, **({"single_flight": metadata} if metadata else {})},
                requirement_hash=sha256(payload.requirement.encode("utf-8")).hexdigest(),
                repository_alias=project.name,
                policy_hash=DEFAULT_POLICY.policy_hash(),
            ),
        )
        session.commit()

        run.current_state = RunStatus.RUNNING
        run.version += 1
        session.commit()
        return run

    def _finish_run(self, session: Session, run: WorkflowRun, result: RunResult) -> WorkflowRun:
        run.current_state = run.result_status = result.result_status
        run.error_code = result.error_code
        run.artifact_directory = None
        if result.artifact_directory:
            candidate = result.artifact_directory.resolve()
            if candidate.is_relative_to(self.artifact_root) and candidate.is_dir():
                run.artifact_directory = candidate.relative_to(self.artifact_root).as_posix()
            else:
                run.current_state = run.result_status = RunStatus.FAILED_SECURITY
                run.error_code = "SINGLE_FLIGHT_ARTIFACT_UNAVAILABLE"
        run.finished_at = datetime.now(UTC)
        run.version += 1
        try:
            session.commit()
        except Exception:
            logger.error(
                "run %s final state commit failed; rolling back (recovery will "
                "resolve the stale state on next startup)",
                run.id,
            )
            session.rollback()
            raise
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

    def _failed_error_code(self, output_dir: Path) -> str | None:
        """Read the runner's persisted error code for a failed run, if any."""
        if output_dir.is_symlink() or not output_dir.is_dir():
            return None
        try:
            directories = [
                path
                for path in output_dir.glob("run-multi-*")
                if path.is_dir() and not path.is_symlink()
            ]
            if len(directories) != 1:
                return None
            run_directory = directories[0].resolve()
            if not run_directory.is_relative_to(self.artifact_root):
                return None
            manifest_path = run_directory / "manifest.json"
            if manifest_path.is_symlink() or not manifest_path.is_file():
                return None
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                return None
            error = manifest.get("error")
            if not isinstance(error, str) or not _SAFE_RUNNER_ERROR_CODE.fullmatch(error):
                return None
            return error
        except (OSError, ValueError):
            return None


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


def get_session(request: Request) -> Generator[Session, None, None]:
    yield from request.app.state.database.sessions()


SessionDependency = Annotated[Session, Depends(get_session)]


def _service(request: Request) -> RunService:
    return RunService(
        RunRepository(),
        request.app.state.artifact_root,
        request.app.state.security.validate_repository_path,
        admit=request.app.state.security.admit_single_flight,
    )


@router.post("", response_model=RunRead, status_code=status.HTTP_201_CREATED)
def create_run(payload: RunCreate, request: Request, session: SessionDependency) -> RunRead:
    try:
        result = _service(request).create(session, payload)
        return _to_read(result)
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
        request.app.state.security.validate_reviewer_label(payload.reviewer_label)
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
        single_flight=(run.state_payload or {}).get("single_flight"),
    )


def _to_decision_read(decision: ReviewDecision) -> ReviewDecisionRead:
    return ReviewDecisionRead(
        id=decision.id,
        decision=decision.decision,
        reviewer_label=decision.reviewer_label,
        rationale=decision.rationale,
        created_at=decision.created_at,
    )
