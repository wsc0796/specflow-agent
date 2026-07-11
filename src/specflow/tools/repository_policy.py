"""Cross-platform safety policy for read-only repository Tools."""

from __future__ import annotations

import fnmatch
import os
import stat
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from specflow.tools.exceptions import (
    RepositoryLimitError,
    RepositoryPathError,
    SensitiveFileError,
)


@dataclass(frozen=True)
class RepositoryPolicyLimits:
    """Hard limits applied by every repository-bound Tool."""

    max_scanned_files: int = 10_000
    max_list_results: int = 1_000
    max_search_files: int = 1_000
    max_search_matches: int = 100
    max_excerpt_chars: int = 240
    max_file_bytes: int = 262_144
    max_patterns: int = 16

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise RepositoryLimitError(f"{name} must be a positive integer")


class RepositoryAccessPolicy:
    """Bind path validation and traversal to one immutable repository root."""

    ignored_directory_names = frozenset(
        {
            ".git",
            ".venv",
            "venv",
            "node_modules",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "dist",
            "build",
        }
    )
    _sensitive_exact_names = frozenset(
        {
            ".env",
            ".npmrc",
            ".pypirc",
            "id_rsa",
            "token.json",
            "tokens.json",
            "service-account.json",
            "service_account.json",
            "application_default_credentials.json",
        }
    )
    _sensitive_suffixes = frozenset({".pem", ".key", ".p12", ".pfx", ".jks"})
    _sensitive_stems = frozenset(
        {
            "access-token",
            "access_token",
            "api-key",
            "api_key",
            "github-token",
            "github_token",
            "private-key",
            "private_key",
            "token",
            "tokens",
        }
    )
    _sensitive_stem_suffixes = frozenset({"", ".cfg", ".ini", ".json", ".txt", ".yaml", ".yml"})

    def __init__(
        self,
        repository_root: Path,
        limits: RepositoryPolicyLimits | None = None,
    ) -> None:
        raw_root = Path(repository_root)
        if not raw_root.exists():
            raise RepositoryPathError("Repository root does not exist")
        if self._is_link_or_reparse_point(raw_root):
            raise RepositoryPathError("Repository root cannot be a link or reparse point")
        try:
            root = raw_root.resolve(strict=True)
        except OSError as exc:
            raise RepositoryPathError("Repository root cannot be resolved") from exc
        if not root.is_dir():
            raise RepositoryPathError("Repository root must be a directory")
        self._root = root
        self.limits = limits or RepositoryPolicyLimits()

    def resolve_file(self, relative_path: str) -> tuple[Path, str]:
        """Resolve one allowed text-file candidate without permitting boundary escape."""
        normalized = self._normalize_relative_path(relative_path)
        self._validate_path_parts(normalized)
        candidate = self._root.joinpath(*PurePosixPath(normalized).parts)
        self._reject_link_components(candidate)
        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError as exc:
            raise RepositoryPathError(f"Repository file does not exist: {normalized}") from exc
        except OSError as exc:
            raise RepositoryPathError(f"Repository file cannot be resolved: {normalized}") from exc
        if not self._is_within(resolved, self._root) or not resolved.is_file():
            raise RepositoryPathError(f"Repository path is not an allowed file: {normalized}")
        return resolved, normalized

    def iter_allowed_files(
        self,
        *,
        include: tuple[str, ...] = (),
        exclude: tuple[str, ...] = (),
    ) -> Iterator[tuple[Path, str]]:
        """Yield allowed files in stable relative-path order."""
        include = self.validate_patterns(include)
        exclude = self.validate_patterns(exclude)
        discovered: list[tuple[Path, str]] = []
        scanned = 0

        for current_root, directory_names, file_names in os.walk(
            self._root,
            topdown=True,
            followlinks=False,
        ):
            current = Path(current_root)
            directory_names[:] = sorted(
                name
                for name in directory_names
                if not self._should_skip_directory(current / name, name)
            )
            for name in sorted(file_names):
                scanned += 1
                if scanned > self.limits.max_scanned_files:
                    raise RepositoryLimitError(
                        f"Repository file scan exceeds limit {self.limits.max_scanned_files}"
                    )
                candidate = current / name
                relative = candidate.relative_to(self._root).as_posix()
                if self.is_sensitive_path(relative) or self._is_link_or_reparse_point(candidate):
                    continue
                if include and not self._matches_any(relative, include):
                    continue
                if exclude and self._matches_any(relative, exclude):
                    continue
                discovered.append((candidate, relative))

        yield from sorted(discovered, key=lambda item: item[1])

    def validate_patterns(self, patterns: tuple[str, ...]) -> tuple[str, ...]:
        """Validate a bounded set of non-escaping glob patterns."""
        if len(patterns) > self.limits.max_patterns:
            raise RepositoryLimitError(f"Pattern count exceeds limit {self.limits.max_patterns}")
        normalized: list[str] = []
        for pattern in patterns:
            if not isinstance(pattern, str) or not pattern.strip():
                raise RepositoryPathError("Patterns must be non-empty strings")
            value = pattern.strip().replace("\\", "/")
            windows_pattern = PureWindowsPath(value)
            if (
                len(value) > 256
                or PurePosixPath(value).is_absolute()
                or windows_pattern.is_absolute()
                or bool(windows_pattern.root)
            ):
                raise RepositoryPathError("Pattern must be a bounded relative glob")
            if ".." in PurePosixPath(value).parts:
                raise RepositoryPathError("Pattern cannot traverse outside repository root")
            normalized.append(value)
        return tuple(normalized)

    def is_sensitive_path(self, relative_path: str) -> bool:
        """Return whether explicit filename rules identify a sensitive path."""
        parts = PurePosixPath(relative_path.replace("\\", "/")).parts
        if any(part.casefold() in self.ignored_directory_names for part in parts[:-1]):
            return True
        name = parts[-1].casefold() if parts else ""
        if name in self._sensitive_exact_names:
            return True
        if name.startswith(".env.") or name.startswith("id_rsa."):
            return True
        if fnmatch.fnmatchcase(name, "credentials.*") or fnmatch.fnmatchcase(name, "secrets.*"):
            return True
        suffix = Path(name).suffix.casefold()
        stem = Path(name).stem.casefold()
        return suffix in self._sensitive_suffixes or (
            stem in self._sensitive_stems and suffix in self._sensitive_stem_suffixes
        )

    def _normalize_relative_path(self, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise RepositoryPathError("Repository path must be a non-empty relative path")
        raw = value.strip()
        windows_path = PureWindowsPath(raw)
        if (
            Path(raw).is_absolute()
            or PurePosixPath(raw.replace("\\", "/")).is_absolute()
            or windows_path.is_absolute()
            or bool(windows_path.root)
        ):
            raise RepositoryPathError("Absolute repository paths are not allowed")
        normalized = raw.replace("\\", "/")
        parts = PurePosixPath(normalized).parts
        if not parts or any(part in {"", ".", ".."} for part in parts):
            raise RepositoryPathError("Repository path traversal is not allowed")
        return PurePosixPath(*parts).as_posix()

    def _validate_path_parts(self, normalized: str) -> None:
        parts = PurePosixPath(normalized).parts
        if any(part.casefold() in self.ignored_directory_names for part in parts[:-1]):
            raise RepositoryPathError("Repository path enters an ignored directory")
        if self.is_sensitive_path(normalized):
            raise SensitiveFileError(f"Sensitive repository file is not readable: {normalized}")

    def _reject_link_components(self, candidate: Path) -> None:
        current = self._root
        try:
            relative_parts = candidate.relative_to(self._root).parts
        except ValueError as exc:
            raise RepositoryPathError("Repository path escapes its bound root") from exc
        for part in relative_parts:
            current = current / part
            if current.exists() and self._is_link_or_reparse_point(current):
                raise RepositoryPathError("Repository path contains a link or reparse point")

    def _should_skip_directory(self, candidate: Path, name: str) -> bool:
        return name.casefold() in self.ignored_directory_names or self._is_link_or_reparse_point(
            candidate
        )

    @staticmethod
    def _matches_any(relative_path: str, patterns: tuple[str, ...]) -> bool:
        return any(fnmatch.fnmatchcase(relative_path, pattern) for pattern in patterns)

    @staticmethod
    def _is_within(candidate: Path, root: Path) -> bool:
        try:
            candidate.relative_to(root)
            return True
        except ValueError:
            return False

    @staticmethod
    def _is_link_or_reparse_point(path: Path) -> bool:
        if path.is_symlink():
            return True
        try:
            attributes = path.lstat().st_file_attributes
        except (AttributeError, OSError):
            return False
        return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
