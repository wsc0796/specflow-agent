# Phase 6A — 执行矩阵(5 cases × 3 pipelines)

| | B1 Single Agent | B2 Legacy 3-worker | B4 6-role Runtime |
| --- | --- | --- | --- |
| pilot_01_single_file | run-B1-01 | run-B2-01 | run-B4-01 |
| pilot_02_two_modules | run-B1-02 | run-B2-02 | run-B4-02 |
| pilot_03_api_config_tests | run-B1-03 | run-B2-03 | run-B4-03 |
| pilot_04_security_reliability | run-B1-04 | run-B2-04 | run-B4-04 |
| pilot_05_vague_requirement | run-B1-05 | run-B2-05 | run-B4-05 |

## 运行规则

- 15 个独立 run 目录,统一根目录:`artifacts/evaluation/pilot-5x3/<case_id>/<pipeline>/`。
- 每轮执行前校验:同 commit、同 model、同预算、同输出 Schema(见 fairness-protocol.md)。
- Pilot 只跑 1 轮;若发现协议/指标不可计算,记录 BLOCKED 项,不重复跑分。
- Phase 7 正式评测再扩展为 30-case(8 单文件 / 10 跨模块 / 8 复杂 / 4 安全),本窗口只预留结构。
