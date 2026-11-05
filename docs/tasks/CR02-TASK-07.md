# CR02 TASK-07：可读交付与查询

日期：2026-11-01。实现基点：`f77cd7cfddf17883f669b3a669ce990fea5f6947`。
状态：本轮工程实现、Astra / xhigh 独立审查与最终离线门禁完成。

用户明确要求继续 TASK-07，复用 checkout、Stop That Shit change、全面离线测试和
`gpt-6-astra / xhigh` 独立审查；不调用真实模型业务通道、不读取凭据、不推送发布。
依据原 v0.2.2 TASK-07 行、C§7.1—7.4、8.1/8.2、9、10.1 及 AC-01/02/04/17/21/24；
同目录修订说明第 6 节勘误继续有效。本文件仅提取当前任务，不重写总规格。

## 交付范围

- 报告 JSON 继续为数据库权威正文；同一认证 GET 支持显式 Markdown 格式。Markdown
  呈现冻结身份、规则/原文/范围、逐检查项、quality、发现、问题、处理任务/依赖/建议范围、
  验收方法和真实执行状态、外部证据原归属与采用/适用性。当前与历史报告严格分离。
  渲染失败不得改动/删除权威报告，不把 NOT_RUN/ready/外部声明显示为已执行或通过。
- 补齐按项目分页的 review 列表、问题/已答状态查询，沿用认证、归属、未知/重复参数拒绝、
  (created_at,id) keyset 和每页上限。状态展示步骤、期限、预算、失败/UNKNOWN 与 dispatch_gate。
- 复用已有事件分页、事件详情和核验 GET/POST。事件正文不可取或完整性不符时明确缺失，
  不以 hash 代替正文；报告保留可定位到本 job 的事件入口。
- 新增现有 `specflow` 下的薄 HTTP CLI：创建/列表/状态/报告/问题/事件、答案/修订、
  核验导入/列表/详情、项目决定查询/发布。POST 原样携带有界 JSON 与用户给出的幂等键；
  不直读写 DB、不执行 procedure、不自动重试或分页扫库。报告默认 Markdown，其余默认 JSON。
  运行时从指定环境变量取得服务认证，禁止命令行明文密钥；本轮测试只注入固定假凭据。
- 用离线 API/CLI 集成反例验证核验三种冲突、成功幂等重放、弱证保存、原归属与当前采用/
  三值适用性，以及导出/渲染故障后权威记录仍可读取。无需新表、依赖或框架。

改动限 contract_review 领域目录、现有 CLI 必要接线、对应测试和任务/完成/恢复报告。
不实现写入、retry 新入口、前缀回放、UI 平台、模型业务实验或旧 runner 旁支修复。

## 测试矩阵

| 边界 | 验证 |
| --- | --- |
| 报告 | JSON 原字义不变；Markdown 完整字段/长尾/不可信内容转义；当前/历史/无报告；渲染失败零写入 |
| 查询 | 项目归属、keyset 同时间戳/页边界/过滤游标；问题答案不跨报告；状态步骤/期限/UNKNOWN/gate |
| 证据 | 事件按 review/job 分页及错误归属；正文/引用/hash/大小缺口；查询不改权威记录 |
| CLI | 只走认证 HTTP、严格子命令/路径、正文有界、无秘密回显、格式/输出故障、无自动执行/重试 |
| 核验 | VERSION_CONFLICT/TARGET_NOT_CURRENT/BASELINE_MISMATCH 分开；旧 key 成功重放优先；弱证与历史采用分别展示 |
| 最终门禁 | 新增定向测试、全仓库 pytest、Ruff check/format、本轮离线 wheel、Astra / xhigh 独立审查及原发现限定复核 |

## 完成证据

最终全仓库 **1513 passed / 3 skipped / 2 warnings，384.69 秒**；contract_review 401 项
全部通过，本轮新增53项。全库 Ruff check/format（277文件）、git diff --check 和本轮离线
1.1.1 wheel 通过。独立 Astra / xhigh 确认的三项 P2 已修复，限定复核原四条 4 passed，
6.26 秒，全部关闭。完整行为、CLI用法、日志及复查命令见 `docs/reports/CR02-TASK-07-completion.md`。
