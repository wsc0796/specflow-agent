import os
import subprocess
from pathlib import Path

import pytest

from specflow.tools import ToolCall, ToolExecutor, ToolRegistry, ToolStatus
from specflow.tools.repository_policy import (
    RepositoryAccessPolicy,
    RepositoryPathError,
    RepositoryPolicyLimits,
)
from specflow.tools.repository_tools import RepositoryToolSet


def _executor(root: Path, **limits: int) -> ToolExecutor:
    registry = ToolRegistry()
    RepositoryToolSet(
        root,
        limits=RepositoryPolicyLimits(**limits),
    ).register_into(registry)
    return ToolExecutor(registry)


def _call(tool_name: str, **arguments: object) -> ToolCall:
    return ToolCall.build(
        call_id=f"call-{tool_name}",
        tool_name=tool_name,
        arguments=dict(arguments),
    )


def test_lists_allowed_files_in_stable_order(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "z.py").write_text("z = 1", encoding="utf-8")
    (tmp_path / "src" / "a.py").write_text("a = 1", encoding="utf-8")

    result = _executor(tmp_path).execute(_call("list_files"))

    assert result.status == ToolStatus.SUCCESS
    assert result.output["files"] == ["src/a.py", "z.py"]
    assert result.output["count"] == 2
    assert result.output["truncated"] is False


def test_list_files_is_stable_across_creation_order(tmp_path: Path) -> None:
    for name in ("c.py", "a.py", "b.py"):
        (tmp_path / name).write_text(name, encoding="utf-8")

    executor = _executor(tmp_path)
    first = executor.execute(_call("list_files"))
    second = executor.execute(_call("list_files"))

    assert first.output == second.output


def test_list_files_supports_bounded_include_and_exclude_patterns(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("app", encoding="utf-8")
    (tmp_path / "src" / "test_app.py").write_text("test", encoding="utf-8")
    (tmp_path / "README.md").write_text("readme", encoding="utf-8")

    result = _executor(tmp_path).execute(
        _call("list_files", include=["*.py"], exclude=["*test_*.py"])
    )

    assert result.output["files"] == ["src/app.py"]


def test_list_files_marks_truncation(tmp_path: Path) -> None:
    for index in range(3):
        (tmp_path / f"{index}.py").write_text("x", encoding="utf-8")

    result = _executor(tmp_path).execute(_call("list_files", max_results=2))

    assert result.output["files"] == ["0.py", "1.py"]
    assert result.output["truncated"] is True


def test_ignored_and_sensitive_paths_are_not_listed(tmp_path: Path) -> None:
    for directory in (
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
    ):
        target = tmp_path / directory
        target.mkdir()
        (target / "hidden.py").write_text("hidden", encoding="utf-8")
    for name in (".env", ".env.local", "server.pem", "id_rsa", "credentials.json"):
        (tmp_path / name).write_text("secret", encoding="utf-8")
    (tmp_path / "environment.py").write_text("safe", encoding="utf-8")

    result = _executor(tmp_path).execute(_call("list_files"))

    assert result.output["files"] == ["environment.py"]


def test_search_code_returns_line_numbers_and_sanitized_excerpts(tmp_path: Path) -> None:
    (tmp_path / "orders.py").write_text(
        "first\nAPI_KEY=top-secret order timeout\norder timeout again\n",
        encoding="utf-8",
    )

    result = _executor(tmp_path).execute(
        _call("search_code", query="order timeout", include=["*.py"])
    )

    assert result.status == ToolStatus.SUCCESS
    assert [match["line_number"] for match in result.output["matches"]] == [2, 3]
    assert result.output["matches"][0]["relative_path"] == "orders.py"
    assert "top-secret" not in result.output["matches"][0]["excerpt"]
    assert result.output["match_count"] == 2


def test_search_code_marks_match_truncation(tmp_path: Path) -> None:
    (tmp_path / "many.txt").write_text("needle\nneedle\nneedle\n", encoding="utf-8")

    result = _executor(tmp_path, max_search_matches=2).execute(_call("search_code", query="needle"))

    assert len(result.output["matches"]) == 2
    assert result.output["truncated"] is True


def test_search_code_skips_binary_and_sensitive_files(tmp_path: Path) -> None:
    (tmp_path / "binary.bin").write_bytes(b"needle\x00value")
    (tmp_path / ".env").write_text("needle", encoding="utf-8")
    (tmp_path / "safe.py").write_text("needle", encoding="utf-8")

    result = _executor(tmp_path).execute(_call("search_code", query="needle"))

    assert [match["relative_path"] for match in result.output["matches"]] == ["safe.py"]


def test_search_code_is_case_insensitive_by_default(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("Order Timeout", encoding="utf-8")

    result = _executor(tmp_path).execute(_call("search_code", query="order timeout"))

    assert result.output["match_count"] == 1


def test_read_file_returns_text_hash_and_relative_path(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_bytes(b"print('ok')\n")

    result = _executor(tmp_path).execute(_call("read_file", path="app.py"))

    assert result.status == ToolStatus.SUCCESS
    assert result.output["relative_path"] == "app.py"
    assert result.output["content"] == "print('ok')\n"
    assert result.output["encoding"] == "utf-8"
    assert result.output["truncated"] is False
    assert len(result.output["content_hash"]) == 64


def test_read_file_truncates_oversized_text(tmp_path: Path) -> None:
    (tmp_path / "large.txt").write_text("abcdefghij", encoding="utf-8")

    result = _executor(tmp_path, max_file_bytes=5).execute(_call("read_file", path="large.txt"))

    assert result.output["content"] == "abcde"
    assert result.output["truncated"] is True


def test_read_file_rejects_binary_file(tmp_path: Path) -> None:
    (tmp_path / "binary.bin").write_bytes(b"text\x00binary")

    result = _executor(tmp_path).execute(_call("read_file", path="binary.bin"))

    assert result.status == ToolStatus.FAILED
    assert result.error_type == "BinaryFileError"


@pytest.mark.parametrize("path", ["../outside.txt", "nested/../../outside.txt"])
def test_read_file_rejects_parent_traversal(tmp_path: Path, path: str) -> None:
    result = _executor(tmp_path).execute(_call("read_file", path=path))

    assert result.status == ToolStatus.FAILED
    assert result.error_type == "RepositoryPathError"


def test_read_file_rejects_absolute_path(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("outside", encoding="utf-8")

    result = _executor(tmp_path).execute(_call("read_file", path=str(outside.resolve())))

    assert result.status == ToolStatus.FAILED
    assert result.error_type == "RepositoryPathError"


@pytest.mark.parametrize("path", ["/etc/passwd", r"\Windows\win.ini"])
def test_read_file_rejects_rooted_paths_without_leaking_root(tmp_path: Path, path: str) -> None:
    result = _executor(tmp_path).execute(_call("read_file", path=path))

    assert result.status == ToolStatus.FAILED
    assert result.error_type == "RepositoryPathError"
    assert str(tmp_path.resolve()) not in result.error_message


@pytest.mark.skipif(os.name == "nt", reason="symlink creation may require Windows privileges")
def test_read_file_rejects_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-secret.txt"
    outside.write_text("outside", encoding="utf-8")
    (tmp_path / "escape.txt").symlink_to(outside)

    result = _executor(tmp_path).execute(_call("read_file", path="escape.txt"))

    assert result.status == ToolStatus.FAILED
    assert result.error_type == "RepositoryPathError"


def test_reparse_point_boundary_logic_never_skips_on_windows(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "safe.txt"
    target.write_text("safe", encoding="utf-8")
    policy = RepositoryAccessPolicy(tmp_path)
    monkeypatch.setattr(policy, "_is_link_or_reparse_point", lambda _: True)

    with pytest.raises(RepositoryPathError, match="link or reparse"):
        policy.resolve_file("safe.txt")


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        ".env.production",
        "private.key",
        "id_rsa",
        "token.txt",
        "api_key.txt",
        "github_token",
    ],
)
def test_read_file_rejects_sensitive_files(tmp_path: Path, path: str) -> None:
    (tmp_path / path).write_text("secret", encoding="utf-8")

    result = _executor(tmp_path).execute(_call("read_file", path=path))

    assert result.status == ToolStatus.FAILED
    assert result.error_type == "SensitiveFileError"


def test_missing_repository_root_fails(tmp_path: Path) -> None:
    with pytest.raises(Exception, match="does not exist"):
        RepositoryToolSet(tmp_path / "missing")


def test_outputs_do_not_contain_repository_absolute_path(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("needle", encoding="utf-8")
    executor = _executor(tmp_path)

    results = [
        executor.execute(_call("list_files")),
        executor.execute(_call("search_code", query="needle")),
        executor.execute(_call("read_file", path="app.py")),
    ]

    assert all(str(tmp_path.resolve()) not in repr(result.output) for result in results)


def test_repository_tools_do_not_modify_repository(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text("needle", encoding="utf-8")
    before = target.read_bytes()
    executor = _executor(tmp_path)

    executor.execute(_call("list_files"))
    executor.execute(_call("search_code", query="needle"))
    executor.execute(_call("read_file", path="app.py"))

    assert target.read_bytes() == before


def test_repository_tool_names_are_registered_explicitly(tmp_path: Path) -> None:
    registry = ToolRegistry()

    RepositoryToolSet(tmp_path).register_into(registry)

    assert [metadata.name for metadata in registry.metadata()] == [
        "list_files",
        "read_file",
        "search_code",
    ]


def test_read_file_redacts_secrets_and_preserves_lines(tmp_path: Path) -> None:
    (tmp_path / "config.py").write_bytes(b"name='safe'\npassword=hunter2\n")

    result = _executor(tmp_path).execute(_call("read_file", path="config.py"))

    assert result.output["content"] == "name='safe'\npassword=<redacted>\n"
    assert "hunter2" not in result.output["content"]


def test_read_file_hash_is_stable(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("value = 1", encoding="utf-8")
    executor = _executor(tmp_path)

    first = executor.execute(_call("read_file", path="app.py"))
    second = executor.execute(_call("read_file", path="app.py"))

    assert first.output["content_hash"] == second.output["content_hash"]


def test_list_files_rejects_result_limit_above_policy(tmp_path: Path) -> None:
    result = _executor(tmp_path, max_list_results=2).execute(_call("list_files", max_results=3))

    assert result.status == ToolStatus.FAILED
    assert result.error_type == "RepositoryLimitError"


@pytest.mark.parametrize("pattern", ["/etc/*", r"\Windows\*"])
def test_list_files_rejects_rooted_patterns(tmp_path: Path, pattern: str) -> None:
    result = _executor(tmp_path).execute(_call("list_files", include=[pattern]))

    assert result.status == ToolStatus.FAILED
    assert result.error_type == "RepositoryPathError"


def test_binary_marker_at_truncation_sentinel_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "mixed.bin").write_bytes(b"abcde\x00tail")

    result = _executor(tmp_path, max_file_bytes=5).execute(_call("read_file", path="mixed.bin"))

    assert result.status == ToolStatus.FAILED
    assert result.error_type == "BinaryFileError"


def test_repository_tools_never_call_subprocess(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("needle", encoding="utf-8")

    def fail(*args, **kwargs):
        del args, kwargs
        raise AssertionError("subprocess must not be called")

    monkeypatch.setattr(subprocess, "run", fail)
    monkeypatch.setattr(subprocess, "Popen", fail)
    executor = _executor(tmp_path)

    assert executor.execute(_call("list_files")).status == ToolStatus.SUCCESS
    assert executor.execute(_call("search_code", query="needle")).status == ToolStatus.SUCCESS
    assert executor.execute(_call("read_file", path="app.py")).status == ToolStatus.SUCCESS
