# CR02 TASK-08：显式重试与已完成前缀复用

任务启动：2026-11-02；收口更新：2026-11-03（Asia/Shanghai）。实施基线：`a7b6f64291d0ffdb4d15f59af9c5c6ed96fb73d2`。
状态：**工程实现、独立审查/限定复核与最终全库门禁完成；本地聚焦交付。**
合同：[TASK-08](../tasks/CR02-TASK-08.md)，含用户本轮同步的 B 方案补充。
任务全局进度和恢复入口见 [TASK-08-progress](CR02-TASK-08-progress.md)。

## 用户可见行为

新增认证 `POST /api/v1/contract-reviews/{review_id}/retries` 和薄 CLI `contract-review retry`。
用户可对当前同输入的最近 failed/interrupted job 显式创建新 attempt：

- `fresh`：保留同一冻结输入，从头新执行，不复用旧模型/子结果，禁止 fallback 字段。
- `reuse_completed`：必须选择 `recovery_fallback=stop|restart_fresh`，从起点按序核对完整接受的前缀。
  命中步骤无新物理派发、无历史 usage 重复结算；自然未完成后缀通过原门禁新执行，此后不再找旧命中。
- 已接受前缀损坏或完整请求、前序、build 无法兼容时使用预选 fallback。权限/归属直接拒绝，
  不可执行 profile 要求新 revision。202 表示 attempt 已创建，不保证能够复用前缀。
- 完整子结果和已接受完整父验收共同构成委派单元；父验收前失败时重新执行该单元。
  adopted/partial/rejected 的完整正文、原始验收与证据用途保留，partial 仍由固定复核检查语义用途。
- 显式规则原文及已投影观察按当前材料授权消费/引用；该消费覆盖不扩大子工具的新读取 grants。
- `GET status` 和 retry 报告 JSON 的 `recovery`、事件详情展示原 job/step/call 来源、模式、边界与实际复用。
  同键同载荷成功重放先于当前版本/状态判断；重复提交不新增 attempt。

调用示例（仅说明接口，不在本轮执行 HTTP/业务模型）：

```powershell
specflow contract-review retry REVIEW_ID --body-file retry.json --idempotency-key retry-01
```

`retry.json` 必填 expected_version、failed_job_id、input_revision_id、reason、mode；
reuse_completed 另填 recovery_fallback。不接受恢复位置、模型或预算覆盖项。
默认 replay 仍关闭，显式 v2 profile 注册 `dynamic_profile(..., replay=True)` 才启用；v1 保持指纹和 fresh 行为。

## 实现与 B 边界

[RetryService](../../src/specflow/contract_review/retries.py) 用原 SQLite 短事务实现幂等、CAS、
归属/profile/容量/累计账检查及同输入新 job，不调用 enqueue_revision，也不复制输入或刷新 grant。
[ReplayRecords/ReplaySession](../../src/specflow/contract_review/replay.py) 分别处理持久 binding 与顺序解析；
Records 仅持存储，Session 仅注入 records、fence 和冻结执行上下文，不持完整 Worker、Provider 或网络客户端。
业务循环仍为 [DynamicRunner](../../src/specflow/contract_review/dynamic_runner.py)，实际 I/O 仍经
[ReviewWorker](../../src/specflow/contract_review/worker.py) 的原持久派发/预算/执行权门禁。

明确分支为命中返回、正常新后缀返回、不可核对的 stop/RestartFresh、非法 ReviewError 拒绝。
requested/effective mode 与是否仍在回放前缀分开；不能将整个 reuse_completed 模式理解为零请求。
restart_fresh 在同一 attempt 放弃当前复用视图、重建 RunState，保留审计、原 deadline、计时起点和累计账。

schema v7 只追加 `contract_review_replay_bindings`；旧迁移/checksum 不变，B 补充没有增加第二次迁移。
新逻辑步骤关联原 step/call/result，完整请求按原样比较，核对接受记录/终态时刻、实际源码 build、
profile 和前序；没有新物理 calls 行、原 usage 重记、删字段制造命中或跨断点拼接。
子结果 binding 保留旧稳定句柄并明确新 attempt 的消费归属，避免复制原 UNIQUE result_ref。
源已接受正文不改写；原调用的可靠 usage、UNKNOWN 与本地收尾仍允许原有受控维护。

## 可复查的受控对照

每一行分别将同一个失败 SQLite 检查点复制为 fresh/reuse 两个 arm，冻结输入、adapter 和故障位置相同。
MockTransport 捕获实际 Provider 请求 JSON，工具执行使用实际 SnapshotTools 计数；真实 HTTP 被阻断。

| 故障位置/场景 | fresh 新模型请求/工具执行 | reuse 新模型请求/工具执行 | 结果 |
| --- | --- | --- | --- |
| 工具读取后、后续模型请求失败 | 3 / 1 | 2 / 0 | 复用已接受模型动作与工具观察，只新执行报告分析/固定复核；报告 payload 相同 |
| 固定复核接受、报告提交前失败 | 3 / 1 | 0 / 0 | 复用完整有效前缀，正式提交报告；报告 payload 相同 |
| 完整委派并 adopted，报告提交前失败 | 5 / 1 | 0 / 0 | 完整子结果＋父验收可复用；报告同口径 |
| 完整委派并 partial，报告提交前失败 | 5 / 1 | 0 / 0 | 部分采用理由和完整原文保留；报告同口径 |
| 完整委派并 rejected，报告提交前失败 | 5 / 1 | 0 / 0 | 拒绝决定和完整诊断保留，不新增肯定证据用途；报告同口径 |
| 子返回但父验收未保存 | 5 / 1 | 5 / 1 | 该委派单元不获复用资格，0 个复用回执 |

完整原始输出与原调用来源见 [evidence-index.json](evidence/CR02-task08-2026-11-02/evidence-index.json)
及其列出的 6 份 comparison JSON。直接路线报告 payload 完全相等；委派路线比较仅规范化
新子任务产生的 child_result_ref，原始最终 payload 全部保留，未改写 oracle。
旧调用 usage/预算条目逐项保持，累计 model_calls 等于旧计数＋新实际派发。
复用回执数不是省下的物理调用数；子复合单元可以只有一个 binding。

以上最终输出均为 `completed_degraded` 的受控报告，不提供业务语义判分；不外推生产费用、Token 节省或准确率。
源码 build 指纹已与归档实际执行的 runtime compatibility 核对一致，见索引字段。

## 验收映射与当前检查

| 合同 | 直接证据 |
| --- | --- |
| T08-01/02 | [test_retries.py](../../tests/contract_review/test_retries.py)：同输入新 job、幂等、CAS、严格请求、认证、存储回滚、profile/预算/在途门禁、waiting＋部分答案重启 |
| T08-03/04 | [test_replay.py](../../tests/contract_review/test_replay.py)：6 个真实计数对照、正常未完成后缀、fresh 独立调用、无新物理行/旧账重记、传递来源 |
| T08-05/06 | 同文件：结果/投影/build/前序/缺记录/完整请求/接受正文/action/父验收损坏，stop/restart_fresh，跨 input 不可 fallback；有时区终态比较 |
| T08-07 | 同文件：adopted/partial/rejected、父验收未保存/晚于终态、子结果包损坏、跨 attempt 完整委派来源 |
| T08-08 | 新 fresh 的依赖重试域与 review 累计计数；原生命周期/队列/预算模块的 UNKNOWN、usage、旧执行权与重复收尾回归 |
| T08-09 | [test_schema_migration.py](../../tests/contract_review/test_schema_migration.py)：v6→v7 additive/回滚/重入和旧数据；[test_review_cli.py](../../tests/contract_review/test_review_cli.py)：认证单请求 retry 与成功重放 |

已取得的定向执行记录（各自对应当时的候选；不把重复节点相加当新样本）：

- [四模块日志](evidence/CR02-task08-2026-11-02/pytest-four-modules.log)：86 passed / 1 warning，142.86s，exit 0。
- [接受记录与时间专项](evidence/CR02-task08-2026-11-02/pytest-new-integrity-focused.log)：9 passed / 24 deselected / 1 warning，21.75s，exit 0。
- [B 边界和对照日志](evidence/CR02-task08-2026-11-02/pytest-b-focused.log)：11 passed / 42 deselected / 1 warning，27.77s，exit 0。

首次扩展验证曾发现权限拒绝被纠正流程改写成通用协议错误，已修复并通过定向回归；
另两项是夹具第三次请求复用幂等键，已修正夹具，未削弱产品幂等保护。原失败和修复日志保留在 TEMP。
上述定向阶段唯一 warning 为现有 Starlette TestClient/httpx 弃用提示；最终门禁如下。

Astra 初审另发现完整委派/传递来源的子前序漏检 T08-F01，已先红灯复现，再统一校验每层源 job
内的完整前序；原生/祖先 root/child 的 stop/restart_fresh 和原对照合计 **18 项定向通过**。
见[红灯](evidence/CR02-task08-2026-11-02/pytest-predecessor-red.log)、[绿灯](evidence/CR02-task08-2026-11-02/pytest-predecessor-green.log)。
旧候选全库因该发现已 ABORTED，不冒充通过；修复后另行执行完整门禁。

修复后首个完整全库运行取得 1680 passed / 1 failed / 3 skipped / 3 warnings，1248.71s，exit 1；
唯一失败为旧迁移测试把成功升级后的版本写死为6，实际数据库为7，故障回滚仍为5。
已仅同步成功版本期望为当前 MIGRATIONS[-1][0]，旧 checksum、输入、备份和回滚断言全保留，
产品代码没有再改；该文件 2 项定向通过（4.98s，exit 0）。
[该次失败全库](evidence/CR02-task08-2026-11-02/pytest-full-before-migration-assert-fix.log) 与
[迁移修复复跑](evidence/CR02-task08-2026-11-02/pytest-migration-assert-fixed.log) 分别保留，
未将子集复跑冒充全库通过；其后另行完成最终完整门禁。

此后补充核对 RuleMaterial/ObservationMaterial 消费边界：原生合法子结果被回放的工具 grants
校验误拒，两项负例复现后作局部消费片段校验修复，不扩大工具权限。
[红灯](evidence/CR02-task08-2026-11-02/pytest-material-consumption-red.log) 后
[14 项定向绿灯](evidence/CR02-task08-2026-11-02/pytest-material-consumption-green.log)，
同一 Astra 限定复核已 CLOSED、总体 PASS。未覆盖该新增边界的前一轮全库已 ABORTED，
随后按修复后冻结候选执行 1686 项最终全库，未将中止结果算通过。

最终完整门禁已通过：**1683 passed / 0 failed / 3 skipped / 3 warnings，2110.23s，exit 0**，
实际收集1686项，含两项新材料消费回归及全部原回放/重试/迁移用例。
[最终全库日志](evidence/CR02-task08-2026-11-02/pytest-final-full.log) 原样归档；六份 comparison JSON
已统一更新为该次完整通过运行的 pytest-229 产物，实际源码 build 与交付候选核对一致。
三项跳过均为 Windows symlink 权限；三项警告为 Starlette/httpx 弃用和两个 TestStrategy 类收集提示。
全库 Ruff check、format --check（296 files）及差异检查通过；未新增跳过/xfail 隐藏失败。

## 可直接使用的两条简历表述与独立验收

以下两条已通过本任务同轮代码/Claim审查及最终门禁，现为可用正文；原保守正文继续有效。
个人贡献沿用已确认的 AI 辅助开发参与范围，不新增独立主导、生产负责或已掌握全部实现的主张。

1. **上下文构建与约束传递：**参与实现多轮契约审查的上下文构建机制：冻结输入与执行配置，保留规则及人工答案原文，按字符预算选择工具观察并记录省略，分离内部返工反馈与人工裁决；核对实际模型请求，验证关键条件与完整人工答案送达。
2. **失败/中断任务重试与前缀复用：**参与实现失败或中断任务的显式重试与有效前缀复用，核验已接受记录、完整请求及委派父验收，仅对未完成后缀新派发；在工具读取后故障的受控离线场景中，新模型请求由 3 次降至 2 次、工具执行由 1 次降至 0 次，最终报告正文一致，旧调用用量不重复结算。

独立 `gpt-6-astra / xhigh` 已在同一轮检查 TASK-08、B 边界及新增简历 Claim，
T08-F01 经修复和限定复核 CLOSED，最终总体 PASS、`blocking_findings=[]`。
显式材料消费误拒补充项也已由同一代理限定复核 CLOSED，所有本轮实质问题已关闭。
实际身份、初审问题及同轮复核见 [Astra 审查记录](CR02-TASK-08-ASTRA-REVIEW-2026-11-02.md)。
没有将上一轮双条 Claim 的 Astra PASS 冒充本次代码验收。

## 未测范围与提交边界

本轮只证明合同内的离线恢复/重试工程行为；真实模型语义与费用收益仍 NOT_RUN。
E03 原完整场景仍缺证，AC-10 整体验收未关闭；TASK-01/02/09 的未完成项见进度表。
不承诺执行栈/任意 DAG 恢复、主动取消、进程强杀、业务写入、副作用 exactly-once 或供应商不重复收费。
保留用户 `CR02-CURRENT.md` 改动，不纳入聚焦提交；本地提交、不推送、不读取凭据/Holdout，不启动旧 automation。
