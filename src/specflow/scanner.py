"""Safe, metadata-only repository traversal for T-003."""

from dataclasses import dataclass
from pathlib import Path


class ScanError(Exception):
    """Base error for a rejected repository scan."""


class InvalidRepositoryPathError(ScanError):
    """The requested root is missing or outside configured allowed roots."""


class FileLimitExceededError(ScanError):
    """The repository contains more files than the configured safe limit."""


@dataclass(frozen=True)
class ScanLimits:
    max_files: int = 10_000
    max_file_size_bytes: int = 1_048_576


@dataclass(frozen=True)
class FileMetadata:
    path: str
    size_bytes: int
    is_oversized: bool


@dataclass(frozen=True)
class ScanResult:
    root: str
    files: list[FileMetadata]
    directories: list[str]
    ignored_directories: list[str]
    total_files: int


class RepositoryScanner:
    """Enumerate safe repository metadata without opening file contents."""

    ignored_directory_names = frozenset({".git", ".venv", "node_modules"})

    def __init__(self, allowed_roots: list[Path], limits: ScanLimits | None = None) -> None:
        self.allowed_roots = [root.resolve(strict=True) for root in allowed_roots]
        self.limits = limits or ScanLimits()

    def scan(self, requested_root: Path) -> ScanResult:
        root = self._validate_root(requested_root)
        files: list[FileMetadata] = []
        directories: list[str] = []
        ignored: list[str] = []

        for current_root, directory_names, file_names in self._walk(root):
            current = Path(current_root)
            relative_current = current.relative_to(root)

            safe_dirs = []
            for name in directory_names:
                candidate = current / name
                if candidate.is_symlink() and not self._is_within(candidate.resolve(), root):
                    continue
                safe_dirs.append(name)
                directories.append((relative_current / name).as_posix())
            ignored.extend(
                (relative_current / name).as_posix()
                for name in directory_names
                if name in self.ignored_directory_names
            )
            directory_names[:] = [
                name for name in safe_dirs if name not in self.ignored_directory_names
            ]

            for name in file_names:
                candidate = current / name
                if candidate.is_symlink() and not self._is_within(candidate.resolve(), root):
                    continue
                files.append(
                    FileMetadata(
                        path=candidate.relative_to(root).as_posix(),
                        size_bytes=candidate.stat().st_size,
                        is_oversized=candidate.stat().st_size > self.limits.max_file_size_bytes,
                    )
                )
                if len(files) > self.limits.max_files:
                    raise FileLimitExceededError(f"File limit exceeded: {self.limits.max_files}")

        return ScanResult(
            root=str(root),
            files=sorted(files, key=lambda file: file.path),
            directories=sorted(directories),
            ignored_directories=sorted(ignored),
            total_files=len(files),
        )

    def _validate_root(self, requested_root: Path) -> Path:
        try:
            root = requested_root.resolve(strict=True)
        except FileNotFoundError as error:
            raise InvalidRepositoryPathError("Repository path does not exist.") from error
        if not root.is_dir() or not any(
            self._is_within(root, allowed) for allowed in self.allowed_roots
        ):
            raise InvalidRepositoryPathError("Repository path is outside allowed roots.")
        return root

    @staticmethod
    def _is_within(candidate: Path, root: Path) -> bool:
        try:
            candidate.relative_to(root)
            return True
        except ValueError:
            return False

    @staticmethod
    def _walk(root: Path):
        import os

        return os.walk(root, followlinks=False)
