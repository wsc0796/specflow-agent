# T-084 — Evidence 来源快照一致性（F2）

- 日期：2026-09-26；状态：FROZEN / approved-for-execution；前序1121ddb。
- 授权：integration-audit-handoff-2026-09-26 F2；search/read之间修改合成文件已复现无提示错配。

## Specification

### REQ-001 — 同版本绑定

每条 search match 携带其读取快照的 content_hash，计算方式与 read_file 一致：对该次有界读取的
完整脱敏内容UTF-8求SHA256，保留原换行。它不是摘录自身hash；truncated=true时不能声称是未读尾部
或原始整文件hash。Collector 只有在所选文件全部 matches 的hash与随后read一致时才使用摘录并绑定hash。

### REQ-002 — 变化/缺失显式处理

多个search间、search/read间版本变化或版本字段缺失时，丢弃该路径全部摘录与source_hash，
给出受控warning并标truncated，不重试、不混用新hash旧excerpt。selected_files仍表示本轮选择尝试。
未变化文件的文本、排序、行号、匹配次数、路径权限、DLP和原预算保持。

### AC-001 — 变更反例

真实ToolExecutor在read前改文件/在两个search之间改文件：无静默版本错配，不交付该路径旧事实，
source_hashes无该路径，有warning。若只剩无效证据，现有runner正常按零可用Evidence处理。

### AC-002 — 未变化/脱敏/截断

LF/CRLF、敏感值与文件上限合成用例：search hash==read hash，hash覆盖完整脱敏读取而非单摘录；
上下游可核对正常excerpts，版本缺失被显式拒绝。原repo tools/Evidence测试通过。

## Design

REQ-001：repository_tools.SearchCodeTool读取后使用既有_sanitize_file_content生成hash，附在每个match，
不改变匹配逻辑。REQ-002：Collector在接受某个路径的摘录之前比较全部match hashes；冲突/缺失只影响
该路径，继续既有有界收集，无额外Tool调用。来源hash的定义沿用现有ReadFileTool，不读第二份源内容求hash。
允许：src/specflow/tools/repository_tools.py、src/specflow/evidence/collector.py、
tests/test_evidence_snapshot_consistency.py、本规格/报告。无检索算法/Schema/旧基准数据变更。

## Tasks

- [x] **TASK-001 — RED→GREEN**：REQ-001、REQ-002，AC-001、AC-002；真实工具合成版本变化反例与正常边界。
- [x] **TASK-002 — 交付**：REQ-001、REQ-002，AC-001、AC-002；受影响回归/Ruff/diff与聚焦提交；
  按交接最终统一跑全量，回退 git revert 本项提交。
