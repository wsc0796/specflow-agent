# T-085 完成报告 — Evidence deadline（F3）

- 日期：2026-09-26；规格：[T-085](../tasks/T-085-evidence-shared-deadline.md)。
- 状态：本项实现与相关验证完成；五项最终全量记录于本轮统一验证报告。

EvidenceCollector 在每次Tool派发前和记录返回结果后执行可选deadline检查。Multi-Agent传入同一个
RuntimeGuard的remaining_time闭包，剩余<=0抛出TIME_BUDGET_EXCEEDED；政策检查在ToolExecutor之外。
runner在Evidence阶段收口政策异常，持久化实际工具调用数与phase=evidence_collection；未完成bundle的
统计省略。默认不传callback的调用方行为保持，零Evidence仍使用原分类。

| AC | 状态 | 实际证据 |
| --- | --- | --- |
| AC-001 | PASS | 工具前已经过期→0调用；list/search/read返回时恰到deadline→后续0调用，无Coordinator/Provider构造，exit3/TIME_BUDGET_EXCEEDED，完整failure manifest |
| AC-002 | PASS | 普通Tool失败同时超时仍保留TIME分类，不泄露合成异常原文；零Evidence/Legacy/工具上限与权限/预算回归通过 |

本批证据根 `specflow-repair-backups/2026-09-26-integration-audit-T082-T086`。
`validate.py t085-red -v tests/test_evidence_deadline.py`：8 failed、1 passed，旧实现过期后继续派发工具。
`t085-green` 包含新测试、Evidence collector/快照、CLI/Multi-Agent、请求预算、执行政策和Run API：
143 passed、1个既有Windows symlink skip、1个既有Starlette warning。HTTP=0；Ruff/format/diff与
规格追溯通过，未修改旧测试。

只阻止新调用及迟到结果继续驱动流程，单次同步文件操作仍需要自行返回，不能强杀。
失败计数省略代表尚无完成bundle统计，不等于零匹配；工具返回记录仍可证明已执行次数。
本项仅collector、runner、新测试、规格/报告；回退git revert本项提交，不推送/发布。
