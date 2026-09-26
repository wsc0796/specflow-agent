# T-085 — Evidence 工具接入 Run deadline（F3）

- 日期：2026-09-26；状态：FROZEN / approved-for-execution；前序6db31a8。
- 授权：integration-audit-handoff-2026-09-26 F3，过期后仍派发工具调用已复现。

## Specification

### REQ-001 — 共享截止时间

Multi-Agent 的 EvidenceCollector 在每次新Tool调用前、返回后检查同一个 RuntimeGuard 的剩余时间。
剩余<=0即抛出TIME_BUDGET_EXCEEDED；不得再派发下一次搜索/读取，也不接受迟到结果驱动下游。
保留单次同步文件操作不能强杀的边界，不新增时钟/异步/重试/线程。

### REQ-002 — 失败收口与兼容

Collector 检查位于 ToolExecutor 之外，政策异常不能被工具普通失败吞掉。runner 在Evidence阶段保存
可定位的 failed/exit3/TIME_BUDGET_EXCEEDED，phase=evidence_collection，不改报零证据。
记录实际已返回工具调用数，尚未完成的收集计数省略，不伪装为0。Callback参数可选，其他Collector
调用方（含Legacy）默认行为不变；正常零Evidence仍为EVIDENCE_NOT_FOUND。

### AC-001 — 精确过期反例

可控Run时钟：首次调用前已经过期时0次；list/search/read返回时恰到deadline后，后续调用为0，
Coordinator/Provider均未创建，退出3并保存安全完整failure Artifact。

### AC-002 — 失败工具与正常回归

普通Tool失败同时过期仍优先传播时间失败；未超时、零Evidence、Tool次数/文件大小/权限、Legacy
和T-079预算相关回归保持。真实HTTP=0，不读取正式数据。

## Design

REQ-001：EvidenceCollector 新增可选 check_deadline: Callable[[],None]，_execute_tool前和记录结果后调用。
runner内闭包使用guard.remaining_time，不创建第二套时钟。REQ-002：runner独立catch SpecFlowError，
复用pre-execution failure写盘；计数允许None并省略，附加可选failure_context，旧无证据路径不变。
允许：src/specflow/evidence/collector.py、src/specflow/runner_multi.py、tests/test_evidence_deadline.py、
本规格/报告。无预算默认、Provider、Scheduler、工具语义、Legacy源码或数据变更。

## Tasks

- [x] **TASK-001 — RED→GREEN**：REQ-001、REQ-002，AC-001、AC-002；真实ToolExecutor＋可控时钟反例。
- [x] **TASK-002 — 验证交付**：REQ-001、REQ-002，AC-001、AC-002；Evidence/Repo/CLI/T079相关回归，
  Ruff/diff与本地聚焦提交；五项最终全量统一收口，回退 git revert 本项提交。
