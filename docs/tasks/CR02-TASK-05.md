# CR02 TASK-05：人工检查点与显式输入修订

日期：2026-10-31。实现基点：e20d707。状态：工程实现与全面离线验证完成。

用户明确要求继续 TASK-05，复用当前 checkout、Stop That Shit change 规则，测试全面，
不调用真实模型、不推送或发布。依据原 v0.2.2 C§3.5、4.5、5.1、8.1/8.2/8.4/8.5、10
及 TASK-05 行；与 TASK-04 恢复记录一致。本文件只提取当前任务，不改总规格。

## 本轮范围

- `POST /api/v1/contract-reviews/{id}/resolution-batches`：严格 select/clarify/
  mark_insufficient 联合，归属/CAS/幂等；部分答案正式保存但不派发；所有阻塞处理后，
  同事务保存完整新输入、唯一 queued job、答案与幂等响应，并原子清空当前报告。
- `POST /api/v1/contract-reviews/{id}/revisions`：明确改变 request/targets/source/
  authority_bindings/ruleset_usage（当前仅 none）/核验选择/profile/本次指令及答案更正；
  拒绝空修订，来源改变重新密封，不变来源复用密封字节。继承累计账，保存变更理由和排除记录。
- schema v4 追加不可变 resolution 表，保留 v1—v3 checksum。当前状态展示剩余阻塞与
  已保存答案；历史报告保持不可变。答案及本次指令完整进入下一实际模型请求和固定复核。
- mark_insufficient 在相同材料下保留不足，不允许相同问题反复阻塞，相关工作保持 not_ready。
  来源、目标或权威绑定改变时显式核对旧答案并记录排除，更正保留原答案与 supersede 关系。

变更限 `src/specflow/contract_review/`、对应 `tests/contract_review/` 和任务报告。
项目长期决定、写入、前缀回放、fresh retry 新入口、UI/薄 CLI 均在后续任务，不提前启用。
无新框架或依赖；工程契约通过不替代真实模型语义验收。

## 测试矩阵

| 层次 | 必测边界 |
| --- | --- |
| HTTP Schema | 三类答案联合；null/未知/不适用字段；严格整数；数量/字数/重复；认证、幂等键及查询参数 |
| 原子性 | 同 review/input/report/question；当前/历史隔离；CAS 并发；整批回滚；部分持久化及重启；最后一项仅一个新输入/job |
| 准入失败 | 运行中拒绝；队列满、累计预算不足、原 profile 不可用、事件/存储失败时答案与入队全部回滚 |
| 输入修订 | 实际变化；快照复用/重新密封；旧报告清空与显式历史查询；检查清单继承；旧答案适用性/更正；核验选择重核 |
| 实际执行 | 等待释放 worker；同材料不同人工答案进入不同下一请求；长答案尾部和固定复核完整；mark_insufficient 不循环重问；累计预算不重置 |
| 兼容与故障 | v3→v4 备份/重入/失败回滚；旧 profile/路由回归；全仓库 pytest、Ruff、离线 wheel |

## 完成结果

最终全仓库 **1389 passed / 3 skipped / 2 warnings，463.37 秒**；contract_review
277 项全部通过。本轮新增 54 个检查点场景和 2 个迁移场景。全库 Ruff check、
format --check（268 文件）、git diff --check 与离线 1.1.1 wheel 构建通过。
完成说明、验收映射及复查命令见 `docs/reports/CR02-TASK-05-completion.md`。
交付为本地聚焦提交，不调用真实模型、不推送或发布。
