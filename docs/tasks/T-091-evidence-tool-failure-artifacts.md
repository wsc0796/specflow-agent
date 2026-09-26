# T-091 — 证据工具失败审计

- 日期：2026-09-26；状态：FROZEN / approved-for-execution。
- 授权：用户确认修复本轮审查的七项问题；基点 5a9000a。

## Specification

### REQ-001 — 行为

list_files 失败立即按安全分类停止采集，不对 None 调 get；multi-agent 证据异常均留下 bounded failure Artifact，exit=3，不构造 Provider。

### REQ-002 — 边界

保留实际 tool_call_count，未知文件数不填0；不泄漏路径或原始异常，不改变可选 search/read 失败跳过和 deadline 分类。

### AC-001 — 主行为

模拟 list_files RepositoryLimitError 得到 EVIDENCE_COLLECTION_FAILED、phase和failed tool元数据、完整性标记，无 NoneType。

### AC-002 — 边界与回归

非预期 collection/setup 异常亦有安全失败记录；零证据、超时、Legacy 原有安全错误输出和正常采集回归通过。

## Design

REQ-001、REQ-002：EvidenceCollectionError 携带可选固定工具名/受控 error_type；collector 检测首个失败；runner 统一安全落盘、记录静态分类，不输出 traceback。
允许：src/specflow/evidence/collector.py、src/specflow/evidence/exceptions.py、src/specflow/runner_multi.py、tests/test_evidence_tool_failure.py、tests/test_cli_multi_agent.py、本规格及报告。
回归发现 CapturingCollector 测试替身没有实际 Collector 的 tool_call_records 属性；补齐空记录接口，不改断言。
禁止：真实 Provider、正式 Dev/Holdout、历史 baseline/raw/学习材料、依赖、权限扩张、全局预算提升、推送。
验证使用净化 Provider 环境且阻断主/子进程 HTTP 的已有包装；临时合成数据独立目录。
回退使用本项聚焦提交的 git revert；不重写旧 Artifact 或历史报告。

## Tasks

- [x] **TASK-001 — 行为回归与实现**：REQ-001、REQ-002；覆盖 AC-001、AC-002，先确认 RED 再修复 GREEN。
- [x] **TASK-002 — 验证与交付**：REQ-001、REQ-002；AC-001、AC-002 相关测试、Ruff/diff、报告与本地提交；最终全量及独立审查统一收口。
