# TASK-06 Astra 独立审查与限定复核

日期：2026-11-01（Asia/Shanghai）。产品目录：`C:/Users/50469/specflow-h04-f03-20261023`。
审查基点：`5e7c78ae6468b851b4a39ae4da17d527450e3998`。

用户指定的独立代理 `/root/task06_astra_review` 以 `model=gpt-6-astra`、
`reasoning_effort=xhigh`、`fork_turns=none` 创建，读取本任务、原规格及当前工作区差异，
包含未跟踪的新模块和测试。审查期间产品代码冻结；代理未修改仓库。

## 结论

确认一项 P3，已修复并经同一代理限定复核关闭；其余本轮范围未确认可行动缺陷。

| 发现 | 具体反例与修复 |
| --- | --- |
| P3 项目决定列表排序不符合 C§8.2 | 原实现按 introduced_version 排序及推进游标。代理通过两个合法 POST，固定相同时间戳并依次生成 pd_z、pd_a；两页实际返回 z、a，规格要求按 (created_at,id) 返回 a、z。固定规则集隔离没有漏项或重复 |
| 修复 | 保留 introduced_version≤固定视图版本的过滤；列表按 (created_at,project_decision_id) 排序，游标位置保存相同二元组，并校验其形状。新增同时间戳反向 ID 及后续发布不污染分页的回归 |

审查范围包括：严格发布/来源联合、项目归属、CAS/幂等/回滚、切片子集与重叠、历史
视图、三值范围匹配、创建/修订的冻结采用、原规则错误支持拒绝、父/子/固定复核正文
消费。没有扩大到旧 runner、写入、retry 新入口、前缀回放或后续 CLI。

## 运行证据

- Astra 首轮独立 TEMP 反例：**1 passed**，确认原 P3。
- 主代理修复回归：**2 passed / 46 deselected，2.56 秒**。
- Astra 限定复核原 P3：**2 passed，1.42 秒**，确认关闭；未扩为新一轮全审。

仓库测试：`tests/contract_review/test_decision_scope.py` 的
`test_pagination_freezes_version_and_rejects_cross_scope_cursor` 和
`test_same_timestamp_pagination_uses_created_at_and_id_with_frozen_view`。
主代理日志：`C:/Users/50469/AppData/Local/Temp/specflow-cr06-pagination-fix-20261101.log`。

上述为离线工程证据；正式业务语义 AC 仍需真实输出和独立 oracle。最终全仓库门禁结果
统一记录在 `CR02-TASK-06-completion.md`，不以审查结论替代运行结果。
