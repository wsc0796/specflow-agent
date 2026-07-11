"""T-002 Project repository, service, and HTTP boundary."""

from collections.abc import Generator
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from specflow.db import Project

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    repository_path: str = Field(min_length=1, max_length=1024)


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    repository_path: str
    latest_scan_id: str | None
    context_version: int
    status: str
    created_at: datetime
    updated_at: datetime


class ProjectRepository:
    def get(self, session: Session, project_id: str) -> Project | None:
        return session.get(Project, project_id)

    def get_by_path(self, session: Session, path: str) -> Project | None:
        return session.scalar(select(Project).where(Project.repository_path == path))

    def add(self, session: Session, project: Project) -> Project:
        session.add(project)
        session.flush()
        return project


class ProjectService:
    def __init__(self, repository: ProjectRepository) -> None:
        self.repository = repository

    def create(self, session: Session, payload: ProjectCreate) -> Project:
        if self.repository.get_by_path(session, payload.repository_path):
            raise ValueError("duplicate path")
        try:
            project = self.repository.add(session, Project(**payload.model_dump()))
            session.commit()
            return project
        except IntegrityError as error:
            session.rollback()
            raise ValueError("duplicate path") from error

    def get(self, session: Session, project_id: str) -> Project:
        project = self.repository.get(session, project_id)
        if project is None:
            raise LookupError("project not found")
        return project


def get_session(request: Request) -> Generator[Session, None, None]:
    yield from request.app.state.database.sessions()


SessionDependency = Annotated[Session, Depends(get_session)]


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, session: SessionDependency) -> ProjectRead:
    try:
        return ProjectRead.model_validate(
            ProjectService(ProjectRepository()).create(session, payload)
        )
    except ValueError as error:
        raise HTTPException(409, "A project with this repository_path already exists.") from error


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, session: SessionDependency) -> ProjectRead:
    try:
        return ProjectRead.model_validate(
            ProjectService(ProjectRepository()).get(session, project_id)
        )
    except LookupError as error:
        raise HTTPException(404, "Project not found.") from error
