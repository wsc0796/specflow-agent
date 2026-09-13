# T-071～T-080 统一规范审查入口

日期：2026-09-13。审查基线：`2959a2f9ac8c7d0d3b5a2217102d0ce0ed223ed0`。

## 本次交付与审查对象

本次应用户要求，将后续十项 T 任务集中到独立分支，供 GPT 审查规范。
十项规范已经存在于上述 `main` 基线，本次只新增这个审查入口；规范正文、
源码、测试、依赖与学习进度均未修改。因此请阅读下面链接的完整规范及其
依赖文档，不能仅依据本 PR 的新增 Diff 判断十项规范是否合理。

这是规范审查材料，不是十项功能的实现报告，也不宣告任务关闭、实施门禁
通过或 M9/M10 验收通过。后续发现的问题应先复验，再在本分支追加相应的
规范修订提交；涉及产品实现的问题应明确归属及实施范围。

## 规范清单与依赖

下表是阅读导航，具体门禁和验收条款以链接的规范原文为准。

| 任务 | 完整规范 | 关键实施前置条件 |
| --- | --- | --- |
| T-071 | [Provider Resilience Guard](../tasks/T-071-provider-resilience-guard.md) | T-070 关闭 |
| T-072 | [Execution Lanes and Bounded Admission](../tasks/T-072-execution-lanes-and-bounded-admission.md) | T-071 关闭 |
| T-073 | [Runtime Saturation and Latency Metrics](../tasks/T-073-runtime-saturation-and-latency-metrics.md) | T-072 关闭 |
| T-074 | [Content-Addressed Evidence and Context Cache](../tasks/T-074-content-addressed-evidence-and-context-cache.md) | T-073 关闭 |
| T-075 | [Unified Run Preflight Validator](../tasks/T-075-unified-run-preflight-validator.md) | T-074 关闭 |
| T-076 | [Java/Maven Repository Profile and cms-flow Benchmark](../tasks/T-076-java-maven-repository-profile-and-cms-flow-benchmark.md) | T-070～T-075 关闭且 runtime review 通过 |
| T-077 | [Guarantee Boundary Ledger and Declaration Registry](../tasks/T-077-guarantee-boundary-ledger.md) | 完整 REQ-M10-12 门禁，包括 M10 冻结批准、声明来源可读、T-070～T-075 各自关闭证据 |
| T-078 | [Deterministic Failpoint Interface and Interrupt Matrix](../tasks/T-078-deterministic-failpoints.md) | T-077 关闭 |
| T-080 | [Evidence and Artifact Integrity Contract Audit](../tasks/T-080-evidence-and-artifact-integrity-audit.md) | T-078 关闭，并完成本任务字段级细化与冻结 |
| T-079 | [Run-Local and Project-Level Assurance Reporting](../tasks/T-079-run-local-and-project-assurance-reporting.md) | T-078、T-080 关闭，并完成本任务字段级细化与冻结 |

M9 顺序为 T-071 → T-072 → T-073 → T-074 → T-075 → runtime review → T-076，
其中入口还要求 T-070 关闭。M10 顺序为 T-077 → T-078 → T-080 → T-079 →
milestone assurance review；T-076 不是 M10 的前置条件。

## 配套材料与版本解释

- [M9 总规范](../tasks/M9-runtime-resilience-efficiency.md)与[M9 冻结报告](M9-specification-freeze-report.md)。
- [M10 总规范](../tasks/M10-runtime-assurance-verification.md)与[M10 冻结报告](M10-specification-freeze-report.md)。
- [任务编号映射](../tasks/TASK-IDENTITY-MAP-2026-09-13.md)：本入口的 T-072/T-073 使用 M9 含义；PR #9 的历史同号修复已映射为 T-083/T-084，学习任务使用 LEARN 编号。
- [T-070 完成报告](T-070-completion-report.md)与[运行时修复集成报告](runtime-repairs-integration-2026-09-13.md)，用于核对前置实现证据。

规范中的 START_HEAD、源代码行号和“当时依赖未满足”等描述属于各自冻结时的
历史快照。审查时应区分声明来源提交、当前审查基线和实际测试提交；若与当前
代码不一致，请记录具体差异，不能把历史观察自动当成当前事实。
PR #11 已合并不等于所有任务的独立关闭门禁已经通过，仍需逐项检查报告与提交。

T-079/T-080 目前冻结的是范围、入口和判断标准，字段级细节保留到前置任务
关闭后细化。请分别判断“当前冻结层级是否足够”和“实施前尚需补齐什么”。

## 给 GPT 的审查请求

请审查本提交中的十项完整规范、两个里程碑规范及配套冻结报告，并结合上述
代码基线检查方案是否仍适用。审查重点如下：

1. 每项任务的目标、允许改动范围、失败语义和验收条件是否一致且可验证。
2. 熔断、重试、执行槽位、single-flight、缓存与 preflight 的责任边界是否
   冲突；异常、超时和取消路径是否有明确归属，是否会重复执行或遗漏释放。
3. legacy、multi-agent、mock 与 Run API 的适用范围是否明确，是否保留既有
   schema、DLP、fail-closed 与产物契约。
4. 依赖链是否闭合，编号是否一致；M10 是否仅验证已有声明，是否清楚区分
   evidence hash、产物字节完整性、freshness，以及单次运行与项目级保证。
5. 规范承诺是否超出单进程边界，测试能否产生足以支持结论的可复现证据。

请按严重程度列出可操作发现，并给出文件/条款、触发条件或反例、影响和最小
修订建议。区分源码/规范发现、实际复现和未验证项；不能访问的材料请逐项列出。
没有执行实验时不要声称已复现；无法证明实施门禁满足时不要宣告可以开始实施。

## 发布验证记录

本节记录本次文档交付的实际验证结果，不代表未来任务的行为验证。

- `uv run pytest -v`：920 passed，3 skipped，3 warnings；3 项跳过均涉及
  Windows 符号链接创建权限。
- `uv run ruff check .`：通过；既有 `tests/test_coordinator.py:113` 的
  `noqa` 指令格式警告仍存在。
- `uv run ruff format --check .`：通过，213 files already formatted。
- 本文 17 个相对文件链接均可解析。
- 对比审查基线，`docs/tasks/`、`src/`、`tests/`、`uv.lock` 和
  `pyproject.toml` 无差异；本次交付仅新增本文。
