# CR02 TASK-06：条件项目记忆 D3-A

日期：2026-11-01。实现基点：`5e7c78ae6468b851b4a39ae4da17d527450e3998`。
状态：本轮工程实现、Astra / xhigh 独立审查及最终离线门禁完成。

用户已授权直接接续 TASK-06，复用当前 checkout，使用 Stop That Shit change；全面离线
测试和 `gpt-6-astra / xhigh` 独立只读审查；本地聚焦提交，不调用真实模型业务通道、
不读取凭据、不推送发布。以下仅提取原规格，不扩写总规格。

依据：原 v0.2.2 TASK-06 行、C§3.3—3.5、4.1—4.4、8.1/8.2/8.7、9、10 及
AC-05/08/13/23；同目录 2026-10-30 修订记录第 6 节勘误继续有效。

## 本轮交付

- 显式启用项目记忆的部署 profile；关闭时项目决定 GET/POST 返回
  `409 OPTION_NOT_ENABLED`，创建/修订仅允许 ruleset_usage=none。
- 认证的 `/api/v1/projects/{project_id}/contract-decisions` GET/POST：严格
  confirm/supersede/withdraw 联合、独立规则集计数、CAS、幂等和原子发布。
  declared/review_record 来源分开；核对同项目、报告、答案和快照片段归属。
- 精确 scope 子集/交集检查；拒绝越界、空交集及与已移除范围相交的切片；部分替代/
  撤回保留旧规则剩余效力。指定历史规则集的视图与固定版本分页不被新发布污染。
- 创建输入在事务中采用明确的 applicable_confirmed 版本；每目标保存不可变原文、
  来源、关系、版本、有效范围表达和采用原因。缺维度继续传播 scope_unresolved。
  仍有效已确认规则不重复批准；来源声明、本 review 答案和模型输出不自动发布。
- 新发布不改 queued/running/完成输入。显式 revision 才切换版本，人工答案派生继续
  原冻结集合；状态显示采用/当前版本。父分析、子任务授权范围与固定复核保留实际正文，
  报告只能引用宿主采用身份，失效规则不得作当前支持。
- schema v5 只追加项目规则集/决定记录，保留 v1—v4 checksum、升级前备份和失败回滚。

修改范围为 `src/specflow/contract_review/`、必要的 `main.py` 接线、对应
`tests/contract_review/`、本任务单和恢复/完成/审查报告。不加框架或依赖。
写入、retry 新入口、前缀回放、后续 CLI/展示以及旧流程旁支问题不在本轮。

## 离线测试矩阵

| 边界 | 必要证据 |
| --- | --- |
| HTTP | 操作/来源联合、严格类型/null/未知字段/上限、认证、幂等键、正文限制和查询 |
| 发布 | CAS 并发、成功重放、不同键/请求、归属、部分替代/撤回、重复切片和存储故障整体回滚 |
| 历史 | 原文保留、版本范围、固定分页、重启重建、旧范围仍有效和错误采用旧规则反例 |
| 输入 | 两个 review 自动复用、版本/范围、同目标 AND、缺路径的差集未知及补齐对照 |
| 冻结 | queued/running/完成不回写、显式采用新版本、答案派生不偷偷升级、准备中版本竞争 |
| 消费 | v1/v2 实际父请求与固定复核完整正文、报告采用版本/原文、失效规则支持拒绝 |
| 兼容 | v4→v5 备份/重入/回滚、旧 checksum/输入不变、全仓库 pytest/Ruff/离线 wheel |

程序测试验证工程契约；真实模型语义 AC 继续等待真实输出与独立 oracle。

## 完成证据

最终全仓库 **1460 passed / 3 skipped / 2 warnings，343.03 秒**；contract_review 348 项
全部通过，本轮新增 66 项。全库 Ruff check/format（272 文件）、git diff --check 和本轮
离线 1.1.1 wheel 通过。Astra / xhigh 独立审查确认的唯一 P3 排序问题已修复并限定复核
关闭。详情见 `docs/reports/CR02-TASK-06-completion.md` 和对应 Astra 审查报告。
