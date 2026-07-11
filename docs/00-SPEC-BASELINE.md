# SpecFlow Agent — frozen MVP baseline

- Source specification: `D:\Downloads\SpecFlow-Agent-v0.3.1.md`
- Version: v0.3.1
- Status: BASELINED
- MVP scope: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy, SQLite, and an
  OpenAI-compatible API only when its later task is reached.

## Non-negotiable development rules

1. Implement one task at a time with a task spec, tests, completion report, and
   focused Git commit.
2. The MVP is frozen. Do not add LangGraph, Redis, vector databases, MCP, Java,
   multi-agent orchestration, or automated bulk code modification.
3. T-001 through T-005 are deterministic and must not call an LLM.
4. The quality gate requires tests, Ruff, documentation synchronization, and
   explicit acceptance evidence.

## Current task

T-003 implements safe, metadata-only repository traversal after T-002 persistence.
It must not perform technology recognition, generate project context, call an LLM,
or mutate workflow state.
