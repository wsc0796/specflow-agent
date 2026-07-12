import subprocess
from pathlib import Path

from specflow.evidence import (
    EvidenceCollectionConfig,
    EvidenceCollector,
    extract_keywords,
)
from specflow.tools import (
    ToolExecutor,
    ToolRegistry,
)
from specflow.tools.repository_tools import RepositoryToolSet


def _executor(root: Path) -> ToolExecutor:
    registry = ToolRegistry()
    RepositoryToolSet(root).register_into(registry)
    return ToolExecutor(registry)


def _collector(root: Path, **config: int) -> EvidenceCollector:
    return EvidenceCollector(
        _executor(root),
        root,
        config=EvidenceCollectionConfig(**config),
    )


def test_keyword_extraction_from_mixed_language() -> None:
    keywords = extract_keywords(
        "Add order timeout auto-cancel using Redis and Celery for order_timeout task"
    )

    assert "order_timeout" in keywords
    assert any("redis" in k.lower() for k in keywords)
    assert any("celery" in k.lower() for k in keywords)


def test_keyword_extraction_adds_deterministic_chinese_code_aliases() -> None:
    keywords = extract_keywords("为订单增加超时自动取消功能，并保证幂等和测试策略")

    assert {"order", "timeout", "cancel", "idempot", "test"}.issubset(keywords)


def test_keyword_extraction_returns_bounded_result() -> None:
    keywords = extract_keywords(
        "add user login logout register profile settings dashboard notification history",
        max_keywords=3,
    )

    assert len(keywords) <= 3


def test_keyword_extraction_includes_technology_hints() -> None:
    keywords = extract_keywords(
        "Add health check",
        technology_hints=("fastapi", "uvicorn"),
    )

    assert "fastapi" in keywords


def test_evidence_collector_lists_matched_and_reads_files(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "orders.py").write_text(
        "class OrderService:\n    def cancel_timeout(self):\n        pass\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "users.py").write_text("class UserService:\n    pass\n", encoding="utf-8")

    bundle = _collector(tmp_path).collect(
        run_id="test-run",
        requirement="订单超时自动取消 order timeout cancel",
        project_summary="sky-takeout Python FastAPI project",
        technology_stack=("fastapi", "sqlalchemy", "redis"),
    )

    assert bundle.run_id == "test-run"
    assert len(bundle.tool_call_records) >= 2
    assert "orders.py" in bundle.selected_files or len(bundle.matched_files) > 0
    assert bundle.evidence_hash
    assert len(bundle.evidence_hash) == 64


def test_evidence_bundle_is_deterministic(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def process_order():\n    pass\n", encoding="utf-8")

    first = _collector(tmp_path).collect(run_id="run-1", requirement="order processing")
    second = _collector(tmp_path).collect(run_id="run-2", requirement="order processing")

    assert first.evidence_hash == second.evidence_hash
    assert first.selected_files == second.selected_files


def test_tool_call_records_are_complete(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("needle", encoding="utf-8")

    bundle = _collector(tmp_path).collect(run_id="run", requirement="needle search")

    assert len(bundle.tool_call_records) > 0
    for record in bundle.tool_call_records:
        assert record.call_id
        assert record.tool_name in {"list_files", "search_code", "read_file"}
        assert record.status in {"success", "failed"}
        assert record.duration_ms >= 0


def test_tool_call_count_is_bounded(tmp_path: Path) -> None:
    for idx in range(5):
        (tmp_path / f"file_{idx}.py").write_text(
            f"order timeout cancel retry #{idx}", encoding="utf-8"
        )

    bundle = _collector(tmp_path, max_tool_calls=3, max_search_keywords=1).collect(
        run_id="run", requirement="order timeout cancel"
    )

    assert len(bundle.tool_call_records) <= 3


def test_sensitive_files_never_enter_evidence(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("SECRET=value", encoding="utf-8")
    (tmp_path / "safe.py").write_text("safe content", encoding="utf-8")

    bundle = _collector(tmp_path).collect(run_id="run", requirement="safe content")

    assert ".env" not in bundle.matched_files
    assert ".env" not in bundle.selected_files


def test_evidence_serialized_context_is_bounded(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("order timeout cancel\n" * 500, encoding="utf-8")

    bundle = _collector(tmp_path, max_total_evidence_chars=1000, max_search_keywords=1).collect(
        run_id="run", requirement="order timeout"
    )

    context = bundle.serialized_context()
    assert len(context) < 10_000


def test_total_evidence_character_limit_is_enforced(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("order timeout cancel\n" * 100, encoding="utf-8")

    bundle = _collector(
        tmp_path,
        max_total_evidence_chars=20,
        max_search_keywords=1,
    ).collect(run_id="run", requirement="order timeout")

    assert sum(len(excerpt.excerpt) for excerpt in bundle.excerpts) <= 20
    assert bundle.truncated


def test_search_keyword_count_is_limited(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("a b c d e", encoding="utf-8")

    bundle = _collector(tmp_path, max_search_keywords=1).collect(
        run_id="run", requirement="a b c d e f g"
    )

    assert len(bundle.searched_terms) <= 1


def test_selected_files_are_ranked_by_match_relevance(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "order_service.py").write_text(
        "order timeout cancel\n" * 10, encoding="utf-8"
    )
    (tmp_path / "utils.py").write_text("order\n", encoding="utf-8")

    bundle = _collector(tmp_path).collect(run_id="run", requirement="order timeout cancel")

    if len(bundle.selected_files) >= 2:
        assert bundle.selected_files[0] == "src/order_service.py"


def test_evidence_bundle_hash_is_stable(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("stable content", encoding="utf-8")

    first = _collector(tmp_path).collect(run_id="a", requirement="stable")
    second = _collector(tmp_path).collect(run_id="b", requirement="stable")

    assert first.evidence_hash == second.evidence_hash


def test_tool_call_record_summaries_are_sanitized(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("api_key=sk-secret-value", encoding="utf-8")

    bundle = _collector(tmp_path).collect(run_id="run", requirement="api_key")

    for record in bundle.tool_call_records:
        assert "sk-secret" not in record.arguments_summary
        assert "sk-secret" not in record.output_summary


def test_repository_tools_never_call_subprocess_during_collection(
    monkeypatch, tmp_path: Path
) -> None:
    (tmp_path / "app.py").write_text("safe", encoding="utf-8")

    def fail(*args, **kwargs):
        del args, kwargs
        raise AssertionError("subprocess must not be called")

    monkeypatch.setattr(subprocess, "run", fail)
    monkeypatch.setattr(subprocess, "Popen", fail)

    bundle = _collector(tmp_path).collect(run_id="run", requirement="safe")
    assert bundle.evidence_hash


def test_collection_does_not_modify_repository(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text("original content", encoding="utf-8")
    before = target.read_bytes()

    _collector(tmp_path).collect(run_id="run", requirement="original")

    assert target.read_bytes() == before
