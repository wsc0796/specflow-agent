"""Explicit Dev loading and an answer-free, versioned source view."""

from __future__ import annotations

import io
import json
import re
import subprocess
import tarfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

SOURCE_PATHS = ("src", "tests", "pyproject.toml", "uv.lock", "README.md")
SOURCE_PROFILE = "authorized-source-v1"
DEV_IDS = tuple(f"SF-RT-D{i:03}" for i in range(1, 21))
CATEGORIES = {
    "exact_keyword": 5,
    "semantic_rewrite": 5,
    "multi_file": 4,
    "no_answer": 3,
    "safety_or_stale_index": 3,
}


@dataclass(frozen=True)
class DevCase:
    case_id: str
    requirement: str
    annotations: dict

    def product_input(self) -> dict[str, str]:
        return {"requirement": self.requirement}


@dataclass(frozen=True)
class DevDataset:
    manifest: dict
    cases: tuple[DevCase, ...]

    @property
    def revision(self) -> str:
        return self.manifest["repository_revision"]


def _plain_path(path: Path) -> None:
    if any(p.is_symlink() or p.is_junction() for p in (path, *path.parents)):
        raise ValueError("Links are not accepted in dataset or snapshot paths")


def _object(path: Path) -> dict:
    _plain_path(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Dataset input must be a JSON object")
    return value


def load_dev_dataset(root: Path) -> DevDataset:
    """Never enumerate JSON files or open a filename supplied by a manifest."""
    manifest = _object(root / "manifest.json")
    if manifest.get("splits", {}).get("dev", {}).get("file") != "dev.json":
        raise ValueError("Only the explicit dev.json input is supported")
    dev = _object(root / "dev.json")
    identity = {
        "suite": "specflow_repository_tasks",
        "dataset_version": "v1",
        "annotation_version": "v1",
        "status": "frozen_v1",
        "repository_revision": manifest.get("repository_revision"),
    }
    if not re.fullmatch(r"[0-9a-f]{40}", str(identity["repository_revision"])):
        raise ValueError("Dataset requires an exact repository revision")
    if manifest.get("frozen") is not True:
        raise ValueError("Dataset must be frozen")
    if not re.fullmatch(r"[0-9a-f]{40}", str(manifest.get("freeze_commit"))):
        raise ValueError("Dataset requires an exact freeze commit")
    split = manifest["splits"]["dev"]
    cases = dev.get("cases")
    if (
        not isinstance(cases, list)
        or len(cases) != 20
        or dev.get("case_count") != 20
        or split.get("case_count") != 20
        or dev.get("split") != "dev"
        or split.get("case_ids") != list(DEV_IDS)
        or any(not isinstance(c, dict) for c in cases)
    ):
        raise ValueError("Dataset must contain exactly the 20 declared Dev cases")
    for value in (manifest, dev, *cases):
        if any(value.get(key) != expected for key, expected in identity.items()):
            raise ValueError("Dataset identity mismatch")
    if (
        sorted(c.get("case_id", "") for c in cases) != list(DEV_IDS)
        or Counter(c.get("category") for c in cases) != CATEGORIES
        or any(c.get("split") != "dev" for c in cases)
    ):
        raise ValueError("Dev IDs, split or category distribution mismatch")
    if any(
        not isinstance(c.get("requirement"), str) or not c["requirement"].strip() for c in cases
    ):
        raise ValueError("Dev requirement must be non-empty text")
    return DevDataset(
        manifest,
        tuple(
            DevCase(c["case_id"], c["requirement"], c)
            for c in sorted(cases, key=lambda item: item["case_id"])
        ),
    )


def validate_frozen_dev(repository: Path, root: Path, dataset: DevDataset) -> None:
    """Compare the explicit Dev file with its freeze commit; never open other splits."""
    relative = (root / "dev.json").resolve().relative_to(repository.resolve()).as_posix()
    result = subprocess.run(
        ["git", "-C", str(repository), "show", f"{dataset.manifest['freeze_commit']}:{relative}"],
        capture_output=True,
        check=False,
    )
    # Git's Windows checkout can convert physical JSON newlines to CRLF.
    # Escaped newlines inside requirement/Gold strings are left untouched.
    frozen = result.stdout.replace(b"\r\n", b"\n")
    current = (root / "dev.json").read_bytes().replace(b"\r\n", b"\n")
    if result.returncode or frozen != current:
        raise ValueError("Dev content differs from the frozen dataset commit")


def source_files(repository: Path, revision: str) -> dict[str, bytes]:
    """Read only a fixed allowlist from Git, without extracting an archive blindly."""
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("An exact source revision is required")
    result = subprocess.run(
        ["git", "-C", str(repository), "archive", "--format=tar", revision, "--", *SOURCE_PATHS],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ValueError("Cannot read the declared source revision")
    files = {}
    with tarfile.open(fileobj=io.BytesIO(result.stdout), mode="r:") as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or "\\" in member.name:
                raise ValueError("Unsafe snapshot archive path")
            if not path.parts or path.parts[0] not in SOURCE_PATHS:
                raise ValueError("Unexpected snapshot archive member")
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError("Snapshot cannot contain links or special files")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("Unreadable snapshot source")
            files[member.name] = stream.read()
    if not files:
        raise ValueError("Empty source snapshot")
    return files


def prepare_source_snapshot(repository: Path, revision: str, target: Path) -> None:
    _plain_path(target)
    if target.resolve() == repository.resolve() or (target.exists() and any(target.iterdir())):
        raise ValueError("Source snapshot destination must be empty and separate from checkout")
    files = source_files(repository, revision)
    target.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def validate_source_snapshot(repository: Path, revision: str, target: Path) -> None:
    _plain_path(target)
    if not target.is_dir() or target.resolve() == repository.resolve():
        raise ValueError("Invalid source snapshot root")
    expected = source_files(repository, revision)
    observed = {}
    for path in target.rglob("*"):
        _plain_path(path)
        if path.is_file():
            name = path.relative_to(target).as_posix()
            if name not in expected:
                raise ValueError("Unexpected file in source snapshot")
            observed[name] = path.read_bytes()
    if observed != expected:
        raise ValueError("Source snapshot content or file list differs from frozen revision")
