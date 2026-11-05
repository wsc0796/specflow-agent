# IMPACT-01 Astra 独立审查

日期：2026-11-02（Asia/Shanghai）。基线：`12aa5b736ba3debccc821219983aa0399892bbe2`。
用户指定 `gpt-6-astra / xhigh / fork_turns=none`，只读审查本任务工作区增量。
不含用户既有 `CR02-CURRENT.md` 修改，不重开 F01 v3 或 TASK-02—07 已关闭审查。

## 初审与修复

| 编号 | 级别 | 原始触发与影响 | 修复及限定证据 | 结论 |
| --- | --- | --- | --- | --- |
| IAR-01 | P2 | 模型调用已持久化 quiesced、结果接受前重启；start 覆盖收尾证据，无槽 interrupted 发现遗留时间预留 | 保留 quiesced；仅在该发现全部调用有收尾证据时结算时间一次；重启前后原始结果仍未接受 | 关闭 |
| IAR-02 | P2 | 合法已读来源引用附带无依据 v999 或 DELETE /不存在路径；可通过 take 创建正式输入 | 版本需完整边界的材料/变更意图支持；method 与完整 path 需同片段依据；未知保留并经人工 edit | 关闭 |
| IAR-03 | P2 | 已受理请求后移除当前 profile；同 key 同正文重放先被 profile 检查拒绝 | 持久幂等重放先于当前 profile 可用性检查；同 key 异正文继续冲突 | 关闭 |

IAR-02 第一次限定复核仍确认两条同类绕过：空搜索的 query 回显被当成事实，
以及 `/exports-v2`、`/exports.json`、`/exports:batch` 被截成 `/exports`。
修复后，观察仅能通过实际投影的 SourceRef 正文提供身份依据；query/目录自我回显不作事实。
路径使用完整文本 token 精确比对，保留标点后缀。该门禁排除无原文依据的身份，
不代替变更关联的业务判断或固定复核。

## 实际复核结果

- 第一轮新增审查回归：`test_impact_review_fixes.py` **6 passed**，IAR-01/03 关闭；
  IAR-02 保留未关闭并继续原反例。
- 第二轮仅复核剩余两条绕过：`test_impact_identity_evidence.py` **7 passed**，
  包括空 query、三种后缀及三条正例；IAR-02 关闭。
- Astra 使用现有 `.venv/Scripts/python.exe`，仅出现既有 StarletteDeprecationWarning。
  最终全仓库门禁另使用已验证的 Python 3.12.10 与本轮 wheel 元数据，数字不混记。

审查者复现使用临时 SQLite、受控 adapter 和原反例，没有修改仓库文件或调用真实模型。
结论：**本次初审确认的 3 项 P2 全部关闭，无确认 P0/P1；没有剩余确认发现，不再扩审。**

## 全量门禁后新增的游标缺陷

首轮全量暴露未知usage用例偶发保存为 EVIDENCE_PERSISTENCE_FAILED。
test-runner 在4次有界复现中捕获原始事务链：USAGE_UNKNOWN 已正常抛出，
随后保存失败状态的 COMMIT 被 SQLite 读锁阻塞，worker 进入存储恢复分类。

新增 test_impact_usage_cursor.py 记录原查询 driver_connection 身份，保持异常 traceback，
占住真实 reader、强制失败提交使用另一 writer，修复前稳定复现 database is locked。
产品最小修复为查询先 `.all()` 耗尽结果再做 `any()`，异常栈不再保留活跃 SQL 游标。
修复后根因回归及原用例主窗口 **2 passed，3.98秒**；Astra 独立限定验证
**2 passed，4.37秒**，确认该项关闭。没有重开前三项或扩展审查。

全部验证与交付状态见 [完成报告](CR02-TASK-IMPACT-01-completion.md)。
