# Phase 5A — 5C 类型检查评估范围

## 现状

- `pyproject.toml` dev 组只有 `pytest` 与 `ruff`;**没有 mypy/pyright**。
- CI(`.github/workflows/ci.yml`)只跑 pytest + ruff + build,无类型检查步骤。
- 代码库使用 `from __future__ import annotations`、dataclass/Pydantic、大量 `dict[str, object]` 边界——类型标注整体质量较好。

## 评估范围(只评核心模块)

建议首轮只检查:

```text
src/specflow/runtime*（runner_multi.py、invoker.py、policy/、coordinator/）
src/specflow/schema/
src/specflow/mcp/
src/specflow/tools/
src/specflow/revision/
src/specflow/plan/
```

## 成本预估

- 引入 `mypy`(或 `pyright`)为新增 dev 依赖;全库 strict 首轮会暴露较多 `dict[str, object]` 索引与 Pydantic 泛型问题。
- 若只对上述核心模块用 `--strict` 起步,预计需要 1 个实现窗口 + 若干 ignore 白名单(不应为全库通过堆 ignore)。
- 当前 `ruff`(E/F/I/UP)+ 777 项测试已提供基本防护;类型检查属于增量保障,不阻塞 Phase 5A/5B。

## 结论

**DECISION_REQUIRED(Phase 5 实现窗口)**:是否引入 mypy(核心模块 strict)还是维持 ruff+pytest。本窗口不引入任何类型检查工具。
