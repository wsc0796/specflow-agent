# T-092 — Artifact 导入结构校验

- 日期：2026-09-26；状态：FROZEN / approved-for-execution。
- 授权：用户确认修复本轮审查的七项问题；基点 5a9000a。

## Specification

### REQ-001 — 行为

公开 validate_live_artifact_import 对合法 JSON 错误结构返回 FAILED/findings，不抛出 AttributeError/TypeError；包括 null 顶层、metadata、source列表及其元素。

### REQ-002 — 边界

保留正常导入、现有路径/DLP/lineage规则；不将坏输入默认为空成功，不以宽泛捕获隐藏实现错误。

### AC-001 — 主行为

manifest=[]/null、trace metadata=null/list、source列表null/string/dict/错误元素均安全失败。

### AC-002 — 边界与回归

正常导入与既有 live import 回归通过，非法 status/tool_name等不可哈希值不会抛错。

## Design

REQ-001、REQ-002：逐边界显式检查类型后取字段，JSON null 记录 invalid_json/shape finding，runner 只从 dict 读取 metadata；限制所有集合成员为正确类型。
允许：src/specflow/evaluation/runner.py、src/specflow/evaluation/validators.py、tests/test_artifact_import_shapes.py、本规格及报告。
禁止：真实 Provider、正式 Dev/Holdout、历史 baseline/raw/学习材料、依赖、权限扩张、全局预算提升、推送。
验证使用净化 Provider 环境且阻断主/子进程 HTTP 的已有包装；临时合成数据独立目录。
回退使用本项聚焦提交的 git revert；不重写旧 Artifact 或历史报告。

## Tasks

- [x] **TASK-001 — 行为回归与实现**：REQ-001、REQ-002；覆盖 AC-001、AC-002，先确认 RED 再修复 GREEN。
- [x] **TASK-002 — 验证与交付**：REQ-001、REQ-002；AC-001、AC-002 相关测试、Ruff/diff、报告与本地提交；最终全量及独立审查统一收口。
