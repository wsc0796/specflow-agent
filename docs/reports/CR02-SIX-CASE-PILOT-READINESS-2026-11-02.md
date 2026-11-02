# 首批六例先导：离线验收准备包

日期：2026-11-02（Asia/Shanghai）。产品目录：`C:/Users/50469/specflow-h04-f03-20261023`。
核对基线：`4f624e2bb513e45b30e3acd5d9eeea7451a0da52`。
状态：**六例材料核对通过，判据可供独立复核；尚不具备六例获准执行条件。**

本包补齐 F02/C01/C03/H01/H02 的逐例判据及人工答案操作，F01 复用
[v3 执行与验收卡](CR02-F01-V3-NEXT-TRIAL-CARD-2026-11-02.md)。它是本次 Goal 的离线交付，
不是新的试验授权或语义验收结果。Oracle 仍待用户独立复核，原材料及判据文件未被改写。

## 1. 固定身份、范围与状态

使用 `ef2c53af26f0a02f61b4e7c8fa07e1d767a17029` 中的公开材料；本轮核对这些材料及
`test_public_fixtures.py` 与该提交无差异。它们属于已知回归，不是 Holdout。
原 manifest 的 24 个 case/trial/sample 身份全部保留，本批只准备其中六例。

| case | 原 trial / sample 后缀 | 来源数 | 正式 target | check key | 当前业务证据 |
| --- | --- | --- | --- | --- | --- |
| CR02-F01 | F01-COMMON-01 | 4 | docs/api.md；examples/client.py | 各 response_field | v1/v2 两次真实失败；v3 尚未跑 |
| CR02-F02 | F02-COMMON-01 | 4 | docs/api.md；examples/client.py | 各 response_field | 无本例真实输出，保持 NOT_RUN |
| CR02-C01 | C01-COMMON-01 | 2 | src/api.py | allowed_states；rejection_code；state_unchanged | 无本例真实输出，保持 NOT_RUN |
| CR02-C03 | C03-COMMON-01 | 2 | src/api.py | allowed_states；rejection_code；state_unchanged | 无本例真实输出，保持 NOT_RUN |
| CR02-H01 | H01-COMMON-01 | 4 | examples/client.py | response_field | 人工 v1 分支尚无真实业务结果 |
| CR02-H02 | H02-COMMON-01 | 4 | examples/client.py | response_field | 人工 v2 分支尚无真实业务结果 |

表中 trial 是 `TR02-<后缀>`，sample 是 `SP02-<后缀>`。F01 的原身份已真实消耗，第二次
执行为 `TR02-F01-COMMON-02`；若再跑须确认新的执行身份。其余原身份是否用于未来首次执行，
也须在获准批次中明确，不能仅因出现在 manifest 就视为已经派发或已获授权。

共 **6 个 case、20 个来源关联、10 份独立 fixture、8 个正式 target、12 个 check**。
这些是初始清单数量；人工答案派生 input/job 不新增独立 case 或 sample。

`manifest.json` 的 D1—D5、live_configuration 及全体 NOT_RUN 是 TASK-01 的历史准备快照，
不能抹去后续 F01 两次失败，也不代表当前完整 B/A/A/C/C 路线被撤销。当前路线与本批执行
授权分别查计划增补和获准试验卡；不把历史 manifest 改成一张混合运行状态表。

## 2. 材料与逐例判据

以下路径为隔离案例仓库内路径，fixture 位于产品目录 `benchmarks/contract_review/materials/`。
每例采用规则和目标正文均须进入相应判断请求；Oracle 的 required_source_paths 应逐项核对。
不要求探索首轮就包含全部正文，也不规定固定读取次数。

### F01：文档与示例都落后于 v2 字段

材料：`contract-v2.json → contracts/v2.json`、`api-correct.py → src/api.py`、
`docs-id.md → docs/api.md`、`example-id.py → examples/client.py`。
采用 v2，检查 `POST /exports` 的创建响应；实现只作对照，正式目标只有文档和示例。

必要结论为两处字段漂移、文档响应示例和示例读取改用 job_id、正确实现保留。
不得把实现改回 id，不得声称已经修改或运行测试；无业务归属不确定项。
要求 job_id 不等于明文禁止兼容 id。具体引用域、正式报告、费用门禁和两次失败证据复用 F01 卡。

### F02：无偏离负控制

材料与 F01 共用契约及正确实现，文档改为 `docs-job-id.md`，示例改为 `example-job-id.py`；
案例内路径与两个正式 target 不变。文档的 201 响应示例使用 job_id，消费代码读取
`response["job_id"]`，均与本次创建字段规则一致。

必要结论是“本次覆盖的 v2 创建响应字段无偏离”，对应两个 check 都有实际检查依据。
不得虚构字段漂移、要求无关人工裁决或声称业务测试通过；无允许的业务不确定项。
没有漂移时不为凑交接格式虚构修改任务，也不能扩大结论为“整个 API 正确”。

最低核对：契约的 `/exports` 创建响应字段、实现返回字段、文档响应示例和示例读取表达式。
四份正文只用于静态比对，不运行被查应用。若实际缺读某项，登记缺证，不能套用预期无偏离。

### C01：completed 被错误放行

材料：`contract-v2.json → contracts/v2.json`，`api-completed-allowed.py → src/api.py`。
正式范围为 v2 `POST /exports/{job_id}/cancel`，只检查实现文件的三个既定 check。
契约允许 queued 取消；running/completed 应拒绝，并保持原状态。

| 给定原状态 | fixture 的静态控制流 | 契约要求 | 判定 |
| --- | --- | --- | --- |
| queued | 通过 running 判断，赋值 cancelled 并返回 | 允许取消 | 保留该合法路径 |
| running | 抛 HTTPException(409, JOB_NOT_CANCELLABLE)，在赋值之前退出 | 拒绝且状态不变 | 保留拒绝保护 |
| completed | 通过 running 判断，赋值 cancelled 并返回 | 拒绝且状态不变 | 必须识别偏离 |

必要结论是 completed 错误放行且改为 cancelled；建议恢复 409/JOB_NOT_CANCELLABLE/
状态不变，同时保留 queued 合法取消。不得放宽契约允许 completed，不得改成禁止所有取消，
不得将静态控制流分析写成运行实测；无允许的业务不确定项。

三个 check 均须有结论：状态集合、拒绝状态码/业务代码、拒绝前后状态。不能只修错误码而
漏掉状态已变，也不能只检查 completed 而忽略合法路径。表中给定任务存在；不存在任务、
并发竞态或新增状态不在本例冻结清单内。

### C03：queued 被错误拒绝

材料同 C01，但实现使用 `api-all-denied.py`。正式接口、目标路径和三个 check 与 C01 相同。
fixture 在读取已有任务后无条件抛出 409/JOB_NOT_CANCELLABLE；后续 cancelled 赋值不可达。

| 给定原状态 | fixture 的静态控制流 | 契约要求 | 判定 |
| --- | --- | --- | --- |
| queued | 无条件拒绝，状态不变 | 允许取消并变为 cancelled | 必须识别偏离 |
| running | 无条件拒绝，状态不变 | 拒绝且状态不变 | 保留拒绝保护 |
| completed | 无条件拒绝，状态不变 | 拒绝且状态不变 | 保留拒绝保护 |

必要结论是 queued 被错误拒绝，恢复合法取消，并保留 running/completed 的拒绝保护。
不得只见 completed 被拒就判整体正确，不得放开非法状态，不得声称运行实测；
无允许的业务不确定项。源码中出现赋值语句不证明该语句可达，必须依据实际控制流判断。

### H01/H02：同初始材料、不同人工归属答案

两例的初始 request 与 sources 完全相同：
`contract-v2.json → contracts/v2.json`、`api-correct.py → src/api.py`、
`contract-v1.json → contracts/v1.json`、`example-ambiguous.py → examples/client.py`。
正式范围仍为 `/exports` 的示例 response_field；v2 是本次采用规则，但示例自身未记录版本。

`example-ambiguous.py` 读取 id；v1 契约要求 id，v2 契约要求 job_id。初始信息不足以确定
示例属于哪个版本，因此必须提出示例版本归属的 blocking scope_choice 问题。
初始允许的不确定性仅为“归属未确定”，不能凭目标的 api_version=v2 就断言材料必属 v2。

| 分支 | 仅在正式问题出现后提交的答案原文 | 答案后的必要结论 |
| --- | --- | --- |
| H01 | 确认 examples/client.py 属于 API v1；其中 id 字段保留，不作为 v2 文档漂移处理。 | 排除该历史示例的 v2 字段漂移，保留 id；旧报告与问题可查 |
| H02 | 确认 examples/client.py 属于 API v2；请按本次采用的 v2 job_id 规则核对该示例。 | 指出示例字段落后，建议读取 job_id；旧报告与问题可查 |

两条答案均为 `answer_type=clarify`、`scope=this_review`。不得把答案放进初始材料或提示，
不得将 local 答案发布为跨审查规则，不得声称已修复。H01 不得初始猜版本，H02 不得照搬
H01 的历史保留结论。两例使用独立 review/答案记录；宿主生成的资源身份可以不同，
用于判断的初始业务内容应一致。

H01/H02 都须证明完整答案原文进入派生 input 的父分析与固定复核请求，并支持后续判断。
仅保存答案、只在报告里提及“用户已确认”、或仅存在答案 hash，均不能代替实际请求证据。

## 3. 人工答案与 revision 的现有接点

依据 `src/specflow/contract_review/checkpoints.py` 的 `ResolutionBatch`、
`CheckpointService.answer` 及 `tests/contract_review/test_checkpoints.py`。
以下是后续获准执行时的操作说明，本轮没有调用接口。

1. 等待当前正式报告进入 `awaiting_decision`。保存其 report_revision_id、input_revision_id、
   当前 status.version 和目标问题。question_id 必须来自该正式报告，确认问题类型、blocking、
   所关联 check 及 allowed_answer_types 接受 clarify；没有合法问题就不预填答案。
2. 使用 `POST /api/v1/contract-reviews/{review_id}/resolution-batches`，携带本操作的
   Idempotency-Key。正文取最新 expected_version、当前 input_revision_id/report_revision_id；
   answers 中填写真实 question_id、this_review、clarify 和上表对应原文。
3. 返回 200 且仍有阻塞时，答案已保存但没有新 job，不另发 revision 强行继续，也不替用户
   编造其他答案。返回 202 表示最后一个阻塞已处理，宿主已原子创建派生 input 和唯一 queued job。
4. 202 后沿响应中的新身份观察同一逻辑任务。旧报告保留，但 current_report 会清空；
   应通过历史 report_revision_id 查询旧报告，不能据当前报告为空认定旧记录丢失。
5. 检查新 input 的 `revision_change.kind=human_answers`、完整 resolutions、同一快照/目标/
   check_manifest/冻结 profile 与累计预算；再核对父分析、固定复核及最终结论。

**回答最后一个阻塞问题已会派生新输入；无需再 POST /revisions 重复派发。**
显式 revisions 用于另行声明的输入/策略变化；更正旧答案需要 supersede_resolution_ids 和
明确 review_directives。该更正分支不是本批 H01/H02 的默认额外试次。

如果真实模型没有形成预期归属问题、只接受 select 而不接受脚本中的 clarify，或产生其他阻塞，
保留实际输出并登记偏差/待决项；不修改问题类型、答案脚本或 Oracle 来追认成功。
答案等待与派生调用都属于同一逻辑 case，费用与物理调用上限不能在派生 input 后重置。

## 4. 统一证据与判定方式

实际载体沿 F01 卡第 6 节：完整 request_projected payload/material_entries、物理请求 wire
与原始模型输出/usage、工具观察、固定复核、报告 JSON/Markdown、身份和费用账及清理记录。
其余五例未来入口可以复用此口径，文件名并不表示当前已经有了运行产物。

逐项复核顺序为：冻结目标/check → 适用规则原文 → 目标正文/观察 → 实际判断请求 →
候选及宿主接受/拒绝 → 固定复核 → 正式报告。H 例再加入旧问题/人工答案/派生 input 的关系。
目录、哈希、工具成功和投影总数均不能单独证明模型读到并正确使用正文。

引用字段语义沿 v3：MaterialRef、SourceRef、observation_id、规则 adoption_id 和外部
evidence_id 不混用。本批没有外部核验导入/采用计划，两个外部核验字段应为空；
业务 execution_status 继续 NOT_RUN。静态审查结果可以完成业务判断，但不能写成测试已执行。

F01/F02/C01/C03 的本例通过条件为：正式报告可查询、固定复核可追溯、全部既定 check
有充分证据和正确判定、必要结论齐全且禁止结论未出现、引用合法、授权与证据完整。
H01/H02 还必须完成合法问题、对应答案原文实际送达、派生输入和分支正确判断的完整链路。
初始合法 `awaiting_decision` 只是人工闭环中间状态，不单独算 H 例完成。

运行前被拦截记 NOT_RUN/具体阻断；已调用后的协议失败或业务误判记失败；证据/远端结果
不明记 UNKNOWN/NOT_ASSESSABLE 并保留消耗。候选部分正确不代替正式报告；
completed/completed_degraded、固定复核 accept 或进程退出码均不能单独签发语义 PASS。
保留 F01 两次失败及以后全部失败/未知，不在看见结果后删例或放宽 Oracle。

## 5. 每例执行缺口与待确认事项

| case | 材料与判据 | 模型/profile | 入口/控制缺口 | 用户仍需确认 |
| --- | --- | --- | --- | --- |
| F01 | v3 卡可审阅；两次失败保留 | v3 为待再次真实验证配置 | 现 guard 固定窗口已过期 | 新 trial、预算/调用/输出上限、窗口及必要 guard 改动 |
| F02 | 无偏离负控制已展开 | 未冻结本例 live profile | 现 runner 只接受 F01 固定身份/材料 | Oracle、纳入批次、模型/profile、运行入口及预算 |
| C01 | 三状态/三检查判据已展开 | 未冻结本例 live profile | 现 runner 的 F01 范围校验不适用 | 同上，保留 queued 正控制和 completed 负控制 |
| C03 | 反向错误判据已展开 | 未冻结本例 live profile | 同上，不可借改 trial-id 冒充 F01 运行 | 同上，保留非法状态保护 |
| H01 | v1 答案分支及隔离要求已展开 | 未冻结本例 live profile | 现 runner 遇 awaiting_decision 即收集退出，缺本例获准的答案续接操作 | 初始/答案后完整逻辑任务、profile、累计预算及操作入口 |
| H02 | v2 答案分支及隔离要求已展开 | 未冻结本例 live profile | 同 H01；必须使用独立 review 和对应答案 | 同上，不因 H01 结果自动采用 v1 答案 |

以上是执行准备缺口，不是本轮新确认的产品实现缺陷。现有 API 具备人工答案派生能力，
不代表 F01 专用 runner 已具备六例编排。不能通过替换 F01 fixture、复用已消耗身份、
修改环境时间或绕过费用 guard 来填补这些缺口。

后续优先顺序仍是：用户复核 F01 v3 卡并决定是否批准一个新 F01 试次；获准后完成必要
试验控制调整与相应离线验证/指定 Astra xhigh 独立代码审查，再执行一次。
其余五例只有在范围、profile、入口和累计费用批准后才进入真实批次，不自动把 F01 的额度
乘以六，也不为等待批准新增无关产品能力。独立的候选影响发现计划继续保留，未在本轮实施。

## 6. 本轮核对与可复查结果

只运行现有材料检查 `tests/contract_review/test_public_fixtures.py`：**9 passed，0.12 秒**。
它验证 24 身份保留/六例集合、逐例路径闭合及 Python AST/JSON 可解析、H 初始输入相同且
后续答案隔离、Oracle 与模型来源分离。它不执行 fixture 应用、不调用模型，也不证明业务语义通过。

本轮另按 cases/manifest/oracles 逐例核对身份与 required_source_paths，计数为
6/20/10/8/12（case/来源关联/独立材料/目标/check）。C01/C03 状态表及 H 答案派生说明
来自本地正文和源码阅读；本轮没有新增受控模型输出，也没有重跑已关闭的全量门禁。

复查命令（在产品 checkout 内执行，使用现有 Python，不同步依赖）：

```powershell
$env:PYTHONPATH = 'C:\Users\50469\specflow-h04-f03-20261023\src'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
& 'C:\Users\50469\AppData\Local\Programs\Python\Python312\python.exe' -B -m pytest -q tests/contract_review/test_public_fixtures.py -p no:cacheprovider
```

原始日志：`C:/Users/50469/AppData/Local/Temp/specflow-six-case-readiness-fixtures-20261102-132805.log`。
文档交付通过 git diff --check；只本地聚焦提交本文件。用户维护的 CR02-CURRENT.md 修改保留。

## 7. 来源索引

- 输入/身份：[cases](../../benchmarks/contract_review/cases.json)、[历史 manifest](../../benchmarks/contract_review/manifest.json)。
- 预期及答案：[oracle](../../benchmarks/contract_review/oracles.json)、[human scripts](../../benchmarks/contract_review/human-scripts.json)；均不进入初始模型材料。
- 范围与历史验证：[TASK-01](../tasks/CR02-TASK-01.md)、[六例材料报告](CR02-TASK-01-early-slice.md)。
- 人工答案实现：[checkpoints.py](../../src/specflow/contract_review/checkpoints.py)、[HTTP API](../../src/specflow/contract_review/api.py)、[TASK-05 报告](CR02-TASK-05-completion.md)。
- 现有检查：[材料检查](../../tests/contract_review/test_public_fixtures.py)、[答案归属/派生/实际请求测试](../../tests/contract_review/test_checkpoints.py)。
- F01 入口：[runner](../../scripts/contract_review/run_f01_pilot.py)、[费用 guard](../../scripts/contract_review/f01_trial_guard.py)、[v3 卡](CR02-F01-V3-NEXT-TRIAL-CARD-2026-11-02.md)。
- 当前计划：`D:/Downloads/agent学习/AI_HANDOFF/2026-10-29-GPT讨论交接/SPEC_FLOW_PLAN_UPDATE_v0.2.3_2026-11-01.md` §5、§7；已有人工范围先导无需等待候选发现开发。

本 Goal 的完成仅指这份可复核的离线准备包交付。它不关闭 TASK-01 全部 COMMON 材料、
完整 TASK-09、上下文 AC-10/E01/E02 或记忆专项，也不授权恢复、条件写入或新真实试验。
