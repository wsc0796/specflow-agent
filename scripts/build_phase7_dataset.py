"""Build the Phase 7 30-case dataset from an authored spec table.

All tasks are authored against the real files of
``benchmarks/fixtures/portfolio-python``.  The script only expands the table
into the frozen JSONL + dataset card; it does not run any pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path

# (case_id, title, requirement, type, difficulty, files, domains, risks,
#  acceptance_topics, forbidden)
TASKS: list[tuple[str, str, str, str, str, tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = [
    # ── Single-file (8) ─────────────────────────────────────────────
    ("f01", "Orders: cancel endpoint validation", "为 app/orders.py 设计取消订单接口的输入校验与错误契约", "bug_fix", "easy", ("app/orders.py",), ("orders", "api", "validation"), ("校验不完整", "错误契约不一致"), ("校验规则", "错误响应"), ("production-ready",)),
    ("f02", "Orders: state transition guard", "为 app/orders.py 的订单状态流转设计不可达状态保护与失败语义", "bug_fix", "easy", ("app/orders.py",), ("orders", "state_machine"), ("非法状态流转",), ("状态机", "失败语义"), ("always works",)),
    ("f03", "Orders: idempotent cancel", "设计订单取消的幂等性,重复取消返回一致结果", "new_feature", "easy", ("app/orders.py",), ("orders", "idempotency"), ("重复请求", "并发"), ("幂等语义",), ("guarantee",)),
    ("f04", "Catalog: listing contract", "为 app/catalog.py 设计商品列表接口的分页与过滤契约", "new_feature", "easy", ("app/catalog.py",), ("catalog", "api"), ("分页越界", "过滤不一致"), ("分页契约", "过滤规则"), ("production-ready",)),
    ("f05", "Cache: TTL policy", "为 app/cache.py 设计缓存 TTL 与失效策略的规格", "new_feature", "easy", ("app/cache.py",), ("cache", "ttl"), ("过期窗口", "一致性问题"), ("TTL 规则", "失效策略"), ("never stale",)),
    ("f06", "Auth: login failure semantics", "为 app/auth.py 设计登录失败的统一错误语义", "bug_fix", "easy", ("app/auth.py",), ("auth", "api"), ("错误泄露",), ("错误契约",), ("production-ready",)),
    ("f07", "Main: route registration spec", "为 app/main.py 设计新增路由的注册与异常处理契约", "refactor", "easy", ("app/main.py",), ("api", "routing"), ("异常泄漏", "路由冲突"), ("路由契约", "异常处理"), ("always works",)),
    ("f08", "Tests: cancel coverage", "为订单取消设计 tests/test_orders.py 的测试矩阵", "test_infra", "easy", ("tests/test_orders.py",), ("testing", "orders"), ("测试缺口",), ("测试矩阵",), ("100% coverage",)),
    # ── Cross-module (10) ───────────────────────────────────────────
    ("f09", "Cache + Catalog integration", "设计缓存层与商品目录的集成方案:命中/失效/回源", "new_feature", "medium", ("app/cache.py", "app/catalog.py"), ("cache", "catalog", "integration"), ("缓存击穿", "失效延迟"), ("集成契约", "失效语义"), ("always fresh",)),
    ("f10", "Auth + Orders authorization", "设计订单取消的鉴权要求:未认证与越权场景", "security", "medium", ("app/auth.py", "app/orders.py"), ("auth", "orders", "security"), ("越权", "未认证"), ("鉴权规则", "越权测试"), ("production-ready",)),
    ("f11", "Orders + Tests contract", "设计订单模块与测试层的契约:测试如何锁定行为", "test_infra", "medium", ("app/orders.py", "tests/test_orders.py"), ("orders", "testing"), ("测试与实现漂移",), ("契约测试",), ("100% coverage",)),
    ("f12", "Main + Orders wiring", "设计 main 路由与订单服务的装配:依赖注入与错误传递", "refactor", "medium", ("app/main.py", "app/orders.py"), ("api", "orders", "wiring"), ("装配错误", "异常吞噬"), ("装配契约",), ("always works",)),
    ("f13", "Catalog + Cache read path", "设计商品读路径:缓存优先、回源、降级", "new_feature", "medium", ("app/catalog.py", "app/cache.py"), ("catalog", "cache", "resilience"), ("降级失败", "数据不一致"), ("读路径契约", "降级策略"), ("never stale",)),
    ("f14", "Auth + Main middleware", "设计认证中间件与路由层的接入点与豁免清单", "security", "medium", ("app/auth.py", "app/main.py"), ("auth", "middleware"), ("豁免泄漏", "中间件顺序"), ("豁免清单", "接入点"), ("production-ready",)),
    ("f15", "Orders + Catalog shared types", "设计订单与目录共享的类型与错误码模块", "refactor", "medium", ("app/orders.py", "app/catalog.py"), ("shared", "types"), ("类型漂移",), ("共享契约",), ("always works",)),
    ("f16", "Cache + Auth token caching", "设计认证令牌的缓存策略(不缓存敏感信息)", "security", "medium", ("app/cache.py", "app/auth.py"), ("cache", "auth", "security"), ("敏感缓存",), ("缓存边界",), ("never stale",)),
    ("f17", "Tests: cross-module flow", "设计 缓存→目录→订单 跨模块流程的集成测试计划", "test_infra", "medium", ("tests/test_orders.py", "app/cache.py", "app/catalog.py"), ("testing", "integration"), ("测试顺序依赖",), ("集成测试矩阵",), ("100% coverage",)),
    ("f18", "Main + Cache warmup", "设计服务启动时的缓存预热与失败容忍", "new_feature", "medium", ("app/main.py", "app/cache.py"), ("startup", "cache", "resilience"), ("预热失败", "启动阻塞"), ("预热契约",), ("always works",)),
    # ── API + config + tests (8) ────────────────────────────────────
    ("f19", "Pagination config", "为列表接口设计分页配置(默认值/上限)与 pyproject 无关的运行时配置", "new_feature", "medium", ("app/catalog.py", "app/main.py"), ("api", "config"), ("配置缺失", "越界"), ("配置契约", "默认值"), ("production-ready",)),
    ("f20", "Error response schema", "设计统一错误响应结构与测试断言", "refactor", "medium", ("app/main.py", "app/orders.py"), ("api", "errors"), ("错误不一致",), ("错误 Schema",), ("always works",)),
    ("f21", "Timeout config", "为外部依赖(缓存/目录)设计超时与重试配置", "reliability", "medium", ("app/cache.py", "app/catalog.py"), ("reliability", "config"), ("超时未处理", "重试风暴"), ("超时契约", "重试策略"), ("never fails",)),
    ("f22", "Test isolation config", "设计测试环境的隔离配置(临时目录/内存缓存)", "test_infra", "medium", ("tests/test_orders.py", "pyproject.toml"), ("testing", "config"), ("测试相互污染",), ("隔离方案",), ("100% coverage",)),
    ("f23", "Auth token TTL config", "设计认证令牌有效期配置与刷新流程", "security", "medium", ("app/auth.py",), ("auth", "security"), ("令牌过期处理",), ("TTL 契约", "刷新流程"), ("production-ready",)),
    ("f24", "Order cancel + API test plan", "为取消接口设计 API 级测试计划(成功/失败/边界)", "test_infra", "medium", ("app/orders.py", "tests/test_orders.py", "app/main.py"), ("testing", "api", "orders"), ("边界遗漏",), ("API 测试矩阵",), ("100% coverage",)),
    ("f25", "Cache stampede protection", "设计缓存击穿保护(单飞/锁)与配置开关", "reliability", "hard", ("app/cache.py", "app/catalog.py"), ("cache", "reliability"), ("击穿", "锁竞争"), ("保护方案", "开关配置"), ("never fails",)),
    ("f26", "Orders: bulk cancel contract", "设计批量取消接口的输入约束、部分失败与幂等", "new_feature", "hard", ("app/orders.py", "app/main.py"), ("orders", "api"), ("部分失败", "幂等"), ("批量契约", "部分失败语义"), ("production-ready",)),
    # ── Security / reliability (4) ─────────────────────────────────
    ("f27", "Auth brute-force limiting", "设计登录限流与失败计数策略", "security", "hard", ("app/auth.py",), ("auth", "security", "rate_limit"), ("暴力破解", "限流误伤"), ("限流规则",), ("production-ready",)),
    ("f28", "Orders race on cancel", "设计取消与提交并发竞争的处理方案", "reliability", "hard", ("app/orders.py",), ("orders", "concurrency"), ("竞态",), ("并发方案",), ("never fails",)),
    ("f29", "Error info leakage", "审计并设计错误响应不泄露内部信息的方案", "security", "hard", ("app/main.py", "app/orders.py", "app/auth.py"), ("security", "api"), ("信息泄露",), ("脱敏规则",), ("production-ready",)),
    ("f30", "Read-only dependency failure", "设计缓存/目录依赖不可用时的降级与失败边界", "reliability", "hard", ("app/cache.py", "app/catalog.py", "app/main.py"), ("reliability", "resilience"), ("级联失败",), ("降级边界",), ("never fails",)),
]


def build(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for index, (case_id, title, requirement, task_type, difficulty, files, domains, risks, topics, forbidden) in enumerate(TASKS, start=1):
        row = {
            "case_id": f"formal_{index:02d}_{case_id}",
            "title": title,
            "requirement": requirement,
            "task_type": task_type,
            "difficulty": difficulty,
            "repository_commit": "a5455e9",
            "repository_path": "benchmarks/fixtures/portfolio-python",
            "expected_file_patterns": list(files),
            "expected_domains": list(domains),
            "expected_risks": list(risks),
            "expected_acceptance_topics": list(topics),
            "forbidden_claims": list(forbidden),
            "acceptable_alternatives": [],
            "required_evidence": list(files),
            "ambiguity_notes": "",
            "human_review_notes": f"Task type: {task_type}; difficulty: {difficulty}.",
        }
        rows.append(row)
    (output_dir / "dataset.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    (output_dir / "dataset-card.md").write_text(
        "\n".join(
            [
                "# Phase 7 Formal Dataset Card (draft)",
                "",
                f"- Total tasks: {len(rows)}",
                f"- Repository: benchmarks/fixtures/portfolio-python @ a5455e9",
                "- Composition: 8 single-file, 10 cross-module, 8 API/config/tests, 4 security/reliability",
                "- Task types: bug_fix, new_feature, refactor, test_infra, security, reliability",
                "- Status: DRAFT_PENDING_FROZEN_EVALUATION_PROTOCOL",
                "",
                "No pipeline receives gold answers; expected surfaces are used only by the scorer.",
            ]
        ),
        encoding="utf-8",
    )
    print(f"wrote {len(rows)} tasks to {output_dir / 'dataset.jsonl'}")


if __name__ == "__main__":
    build(Path("evaluation/formal"))
