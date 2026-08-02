# Phase 6A — Pilot 任务集设计(只读准备)

窗口:phase6a(由 phase_4a_live_prep 窗口代为执行)· 分支:fix/phase-6a-pilot-design · Base commit:bc76214

## 1. 设计约束

- 所有 5 个案例共用同一 fixture 仓库:`benchmarks/fixtures/portfolio-python`(app/auth.py、app/cache.py、app/catalog.py、app/main.py、app/orders.py、tests/test_orders.py、pyproject.toml、README.md),保证公平性,不引入私有路径。
- 案例 JSON 与 `specflow/evaluation/models.py::EvaluationCase` 字段一一对应,可直接被 `evaluation/runner.load_cases()` 加载。
- 任务文本是"生成实施计划/规格"型任务,符合 SpecFlow 定位;评分只看产出规格的证据质量,不看代码是否已实现。

## 2. 五类任务

| case_id | 类别 | 聚焦文件 | 核心考察点 |
| --- | --- | --- | --- |
| pilot_01_single_file | 单文件 | app/orders.py | 精确到单文件的计划、状态机与校验 |
| pilot_02_two_modules | 两模块 | app/cache.py + app/catalog.py | 跨模块数据流、缓存失效归属 |
| pilot_03_api_config_tests | API+配置+测试 | app/main.py、app/orders.py、tests/test_orders.py、pyproject.toml | 配置 Schema、错误契约、测试计划 |
| pilot_04_security_reliability | 安全/可靠性 | app/auth.py、app/orders.py、app/main.py | 认证、竞态、错误泄露、限流 |
| pilot_05_vague_requirement | 模糊需求 | app/*.py(全仓) | 不确定性声明、范围收敛、禁止过度承诺 |

## 3. 执行规则(Phase 6F 前冻结)

1. 三管道同一 commit、同一 model/参数/evidence/工具/token 预算/wall-clock/输出 Schema/失败规则(见 fairness-protocol.md)。
2. 每个 case × pipeline 独立 run 目录,产物互不覆盖。
3. 全部 15 次运行使用 mock 之外的真实 provider 前,必须先完成 Phase 4B 用户批准与 Phase 6F 批准。
4. Pilot 不产生任何质量结论;只做协议验证、指标稳定性检查。

## 4. 与现有评测层的衔接

- 自动化契约:复用 `evaluation/validators.validate_artifacts` + 新增 6G 指标(见 scoring-rubric.md)。
- 人工盲评:复用 `RUBRIC_DIMENSIONS` / `AB_DIMENSIONS` 语义,6H 采用独立盲评窗口。
- 指标采集:复用 `RunMetrics` 字段(Phase 3 已统一),6E 只补充成本字段(见 cost-collector-fields.md)。
