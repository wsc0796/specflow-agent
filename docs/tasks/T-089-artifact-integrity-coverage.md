# T-089 — Artifact 哈希覆盖校验

- 日期：2026-09-26；状态：FROZEN / approved-for-execution。
- 授权：用户确认修复本轮审查的七项问题；基点 5a9000a。

## Specification

### REQ-001 — 行为

multi-agent 检查要求 artifact_hashes 精确覆盖七个数据文件，拒绝空表、缺项、额外路径和非法 digest；文件是普通无链接且在目录内。

### REQ-002 — 边界

校验失败只返回分类 findings，不读哈希表指定的任意路径；正常产品 Artifact 和既有历史有效结构继续通过。

### AC-001 — 主行为

损坏 agent-outputs 加空/漏项哈希表判 fail；正确哈希和全集合判 pass。

### AC-002 — 边界与回归

路径穿越、绝对路径、非法 hash、内容失配和链接判 fail；不读取外部文件。

## Design

REQ-001、REQ-002：将必需数据文件与标记/完整性文件区分，先验证集合，再按固定 allowlist 读取/核验，沿用原观测结果接口。
允许：src/specflow/evaluation/dev_baseline.py、tests/test_artifact_integrity_coverage.py、本规格及报告。
禁止：真实 Provider、正式 Dev/Holdout、历史 baseline/raw/学习材料、依赖、权限扩张、全局预算提升、推送。
验证使用净化 Provider 环境且阻断主/子进程 HTTP 的已有包装；临时合成数据独立目录。
回退使用本项聚焦提交的 git revert；不重写旧 Artifact 或历史报告。

## Tasks

- [x] **TASK-001 — 行为回归与实现**：REQ-001、REQ-002；覆盖 AC-001、AC-002，先确认 RED 再修复 GREEN。
- [x] **TASK-002 — 验证与交付**：REQ-001、REQ-002；AC-001、AC-002 相关测试、Ruff/diff、报告与本地提交；最终全量及独立审查统一收口。
