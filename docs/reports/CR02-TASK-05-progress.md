# TASK-05 最终恢复记录

## 2026-11-01 Astra 复审修复（已完成）

用户指定 `gpt-6-astra / xhigh`，独立审查 6271998 发现两项 P2：未声明 profile 漂移、
mark_insufficient 误伤同目标独立工作。已在原 TASK-05 范围修复，Astra 限定复核原两项
通过（原反例 2 passed / 4.85 秒）。详见 `CR02-TASK-05-ASTRA-REVIEW-2026-11-01.md`。
新增 `test_checkpoint_review_fixes.py` 五个场景；全库 Ruff 269 文件通过。首次全量
1393 passed / 1 failed（旧 scheduler 的20ms时序断言）；对应模块复测15 passed，未改旧代码。
保持相同代码重跑完整门禁已通过：**1394 passed / 3 skipped / 2 warnings，353.91 秒**，
其中 contract_review 282 项全部通过，旧调度器用例也通过。最终日志
`C:/Users/50469/AppData/Local/Temp/specflow-cr05-astra-fixed-pytest-20261101-retry.log`。
首轮日志仍保留在同目录去掉 -retry 的文件。
本轮 wheel 在同 TEMP 下 `specflow-cr05-astra-fixed-build-20261101/`。修复基点为 6271998，
代码、回归与报告作为一个本地聚焦提交交付，不推送发布。当前授权修复已结束，无运行中测试。

收到旁支只读同步：来源 chat `01a19226-c091-76d1-82b0-6cc1a2ce99d2`，检查 HEAD
同为 6271998；未修改文件或影响测试。旁支报告旧 runner_multi 的失败阶段内成功兄弟产物
未独立保存、证据引用仅结构校验、Reviewer 缺原始证据输入；旧失败后已接纳的先前阶段仍
会保存，不能扩大为“所有后续失败都丢结果”。新流程的片段授权、引用校验及父验收有不同
边界，不能套用旧结论。恢复目前是状态收尾，成功节点复用/续跑属于未实现能力。
这是旁支证据同步，主窗口未在本轮重复复现，也未新增修复授权；只作为后续候选保留。
后续顺序建议为有效产物独立保存 → 冻结复用语义 → 有界续跑，保留固定 DAG 与新父子委派。
原建议附件：`C:/Users/50469/.codex/attachments/6b330ba8-2f4a-4d8d-b1aa-e9fc0c33ae65/已粘贴的文本.txt`。

以下为 2026-10-31 首次交付记录；其测试数字不代替本轮最终门禁。

日期：2026-10-31（Asia/Shanghai）。产品目录：`C:/Users/50469/specflow-h04-f03-20261023`。
实现基点：`e20d7077d16ada8ecdd4978ede2341679f7e7f53`。状态：工程实现与最终离线门禁完成。
正式说明：`docs/reports/CR02-TASK-05-completion.md`；当前中枢：`CR02-CURRENT.md`。

用户明确继续 TASK-05，复用 checkout、Stop That Shit change，测试全面；不调用真实模型、
不推送或发布。原规格提取见 `docs/tasks/CR02-TASK-05.md`，没有扩写总规格。
上下文监督本轮开始为 healthy。无新框架或依赖；不读取凭据/Holdout，不运行旧评测。

## 已完成

- `src/specflow/contract_review/checkpoints.py`：答案判别联合、部分持久化、最后阻塞的
  原子派生；显式 revision、密封快照复用/重建、实际变化检查、旧答案适用性和 supersede。
- `api.py`：resolution-batches/revisions 两个 POST，沿用认证/body 上限/幂等/查询校验。
- `service.py`：检查点服务、剩余阻塞与答案投影，复用原累计账与 enqueue_revision。
- `store.py`：v4 追加 resolutions，保持 v1—v3 checksum。
- `worker.py` / `dynamic_context.py`：完整答案与 review_directives 进入父分析/固定复核。
- `report_validation.py`：mark_insufficient 同材料不循环阻塞，相关工作 not_ready、覆盖保留缺口。
- `tests/contract_review/test_checkpoints.py`：54 个新场景；测试子代理仅修改此文件且已结束。
- `tests/contract_review/test_schema_migration.py`：保持旧迁移测试目标，补 v3→v4 成功/
  备份/重入/失败回滚两项参数化场景。

部分已答问题原来只在 resolution 表；显式 revision 合并该报告持久答案后再核对适用性和
更正，避免遗漏。新输入保存采用/排除或 supersede 理由，原答案不改写。同有效 profile
的显式选择不构成空跑入口。历史报告保持不可变，新输入/job 排队与清空当前报告同事务。

## 最终验证

| 检查 | 结果 |
| --- | --- |
| 迁移/上下文/报告校验聚焦 | 47 passed，15.91 秒 |
| 新检查点最后受影响定向 | 12 passed / 42 deselected，31.18 秒 |
| 最终全仓库 pytest | **1389 passed / 3 skipped / 2 warnings，463.37 秒** |
| 全量内 contract_review | **277 项全部通过**，较 TASK-04 新增 56 项 |
| 全库 Ruff check / format --check | 通过，268 个 Python 文件 |
| git diff --check | 通过 |
| 离线 wheel | 1.1.1 构建成功，检查点模块已核实打包 |

三个跳过和两个警告均为原有条件，无新增 skip/xfail。首批测试暴露旧最小报告上下文不带
resolutions 的兼容问题，已修复；接口首批失败为测试误用历史查询路由，已改为既有
`/report?report_revision_id=...`。最终全量重新覆盖全部新旧测试并通过。

日志：`C:/Users/50469/AppData/Local/Temp/specflow-cr05-final-pytest-20261031.log`。
构建：`C:/Users/50469/AppData/Local/Temp/specflow-cr05-final-build-20261031/specflow_agent-1.1.1-py3-none-any.whl`。
现有 Python 3.12.10 与 uv no-project offline；src 优先，本轮 wheel 提供 1.1.1 元数据。
关闭外部 pytest 插件/bytecode，测试子进程按名称移除四项 Provider 配置，conftest 阻断真实
HTTP。复查命令见正式完成报告。当前实现、任务和报告作为同一个本地聚焦提交交付。

## 下一步边界

TASK-05 当前授权范围已结束；后续项目决定、写入、回放、retry 新入口和查询/CLI 改进
按各自独立任务及授权推进，不重复已通过门禁或 TASK-02/03 前置审查。真实模型的答案
理解与业务判断仍须真实输出和独立 oracle，不以程序测试关闭对应语义验收。
