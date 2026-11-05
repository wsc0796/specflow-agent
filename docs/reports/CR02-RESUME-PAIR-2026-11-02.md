# SPEC-FLOW：两条简历表述与聚焦验收

日期：2026-11-02（Asia/Shanghai）。正文版本：`PAIR-v1`。
产品/审查基线：`5d93e7b17bf65556f9c3e766472d9eb937c0f15e`。
状态：**两条正文均经独立 Astra 验收 PASS，无未关闭实质问题，可用于当前工程参与范围的简历表述。**
执行合同：[v0.2.4 今日双条交付](D:/Downloads/agent学习/AI_HANDOFF/2026-10-29-GPT讨论交接/SPEC_FLOW_PLAN_UPDATE_v0.2.4_2026-11-02.md)。

## 最终正文

1. **上下文构建与约束传递：**参与实现多轮契约审查的上下文构建机制：冻结输入与执行配置，保留规则及人工答案原文，按字符预算选择工具观察并记录省略，分离内部返工反馈与人工裁决；核对实际模型请求，验证关键条件与完整人工答案送达。
2. **受控执行与故障处理：**参与实现基于 SQLite 事务的 Agent 调用账本，调用前持久化请求及预算占用，记录失败时阻断派发；通过执行权校验与在途调用状态管理，验证超时迟到结果拒收、可靠收尾后排队任务继续，以及重启后的旧执行权失效。

两条分别说明材料如何送达、调用如何受控，贡献动词均限定为“参与实现”。个人角色沿用已确认的
AI 辅助开发参与范围，不从源码或测试通过推导独立编码、独立主导、生产负责或已掌握全部实现。
验证结果均为离线程序边界；两条不包含业务成功率、收益数字或真实模型正确理解的承诺。

## 精简证据矩阵

核查方法：本轮读取源码、归档 JSON 和既有真实执行日志（`inspected_source`、`inspected_report`）；
没有重跑上下文专项、全库测试或业务模型，也没有新增 probe。

| Claim | 实现与准确证据 | 判定与适用范围 |
| --- | --- | --- |
| C1 冻结输入/配置、保留原文、预算与反馈分离 | [freeze_input](../../src/specflow/contract_review/inputs.py#L47)、[上下文装配](../../src/specflow/contract_review/dynamic_context.py#L80)、[观察预算](../../src/specflow/contract_review/dynamic_context.py#L191)、[内部反馈](../../src/specflow/contract_review/dynamic_runner.py#L201)、[人工答案入库及修订](../../src/specflow/contract_review/checkpoints.py#L200)；[既有 Claim/测试/日志映射](CR02-CONTEXT-RESUME-EVIDENCE-2026-11-02.md) | 已验证；离线机制，不是 Token 压缩或整场会话冻结 |
| C2 实际请求中关键条件与人工原文送达 | [E01](evidence/CR02-context-2026-11-02/E01-ordinary-tool-tail.json)：普通工具观察正文 900 字符，条件在 offset 841，进入 wire 索引 1/2；[E02-v1](evidence/CR02-context-2026-11-02/E02-human-v1-internal-feedback.json)/[E02-v2](evidence/CR02-context-2026-11-02/E02-human-v2-internal-feedback.json)：各两条人工答案与不同内部反馈在索引 4/5 同时存在，DB resolutions 仅有人工答案；[原执行日志](evidence/CR02-context-2026-11-02/pytest-probes-02.log) L6–10 | 关联程序变体 PASS；原 3 个用例通过，15 条 wire 与落库投影相等、27 个细检查，不是 15/27 个独立语义案例。真实语义 NOT_RUN |
| R1 请求意图记录失败零派发 | [事务](../../src/specflow/contract_review/store.py#L133)、[预留与投影](../../src/specflow/contract_review/dynamic_ledger.py#L38)、[调用启动门](../../src/specflow/contract_review/worker.py#L163)；生命周期测试 [L172](../../tests/contract_review/test_lifecycle_and_queue.py#L172) 的 adapter.requests=[] / model_calls=0，对应旧日志 L359；共享影响发现测试 [L594](../../tests/contract_review/test_impact_discovery.py#L594)，旧日志 L326；调用前已落库的回调断言为生命周期 [L80](../../tests/contract_review/test_lifecycle_and_queue.py#L80)，旧日志 L357 | PASS，范围分别为 v1 生命周期与共享/影响发现分支；v2 动态请求使用同一事务封装和启动门，属于本轮源码核对，不冒充新增的 v2-only 零派发运行 |
| R2 未知在途阻断新派发 | [超时与启动门](../../src/specflow/contract_review/worker.py#L163)；生命周期 [L124](../../tests/contract_review/test_lifecycle_and_queue.py#L124)，旧日志 L358：第二作业 queued、请求数仍为 1；v2 子调用 [L598](../../tests/contract_review/test_dynamic_workflow.py#L598)，旧日志 L230：第二作业 queued、请求数仍为 2；共享双向测试 [L556](../../tests/contract_review/test_impact_discovery.py#L556)，旧日志 L324–325 | PASS，分别保留 v1、v2 子调用与共享双向范围；未确认本地收尾时不释放调用槽 |
| R3 可靠收尾后后续队列继续、迟到正文拒收、重复收尾不释放新槽 | [维护收尾](../../src/specflow/contract_review/worker.py#L112)、[实例/槽匹配及幂等收尾](../../src/specflow/contract_review/execution.py#L483)；生命周期 L138–168 / 旧日志 L358：第二作业最终 completed_degraded，旧调用 result/acceptance=None、UNKNOWN 且 quiesced，重复 settle=False 且第二槽仍被占用；v2 L610–627 / 旧日志 L230；v2 存储恢复 [L719](../../tests/contract_review/test_dynamic_workflow.py#L719) / 旧日志 L238 | PASS。重复收尾不释放后续槽的直接运行证据来自 v1；v2 独立覆盖子调用迟到拒收及存储恢复后队列继续。继续的是后续 queued 作业，失败原作业没有续跑 |
| R4 重启分类、queued 保留及旧执行权拒绝 | [启动分类](../../src/specflow/contract_review/execution.py#L23)、[执行权检查](../../src/specflow/contract_review/execution.py#L58)、[动态继承](../../src/specflow/contract_review/dynamic_ledger.py#L12)、[共享路由](../../src/specflow/contract_review/shared_ledger.py#L7)；生命周期 [L202](../../tests/contract_review/test_lifecycle_and_queue.py#L202) / 旧日志 L361；共享影响发现 [L613](../../tests/contract_review/test_impact_discovery.py#L613) / 旧日志 L327；状态/用量分离 [L272](../../tests/contract_review/test_lifecycle_and_queue.py#L272) / 旧日志 L364 | PASS，受控 owner 切换及退出证据注入；没有做真实 OS 杀进程恢复试验。running→interrupted、旧 fence/fail 拒绝；UNKNOWN 与本地 quiesced、远端成功及用量是否已知分别记录 |

运行证据的权威索引为 [runtime-evidence-index.json](evidence/CR02-runtime-2026-11-02/runtime-evidence-index.json)，
逐条保留准确 test node、原日志行、断言范围和适用分支；[reused-pytest-excerpt.log](evidence/CR02-runtime-2026-11-02/reused-pytest-excerpt.log)
归档 11 个既有 PASS 节点及原全量摘要。它们是旧执行结果，本次没有伪造或重新导出运行状态数据。
原日志：`C:/Users/50469/AppData/Local/Temp/specflow-impact-final-fixed-pytest-20261102-152722-485.log`。

该日志所对应的代码基线为 `14209183929dd19a566803e04897d246efdc3cd8`；本次已用
`git diff --exit-code 14209183929dd19a566803e04897d246efdc3cd8 HEAD -- src tests benchmarks`
确认与交付基线产品树相同（exit 0）。原全库 1617 passed / 3 skipped / 2 warnings 仅作门禁来源，
不进入简历正文，不当作运行可靠性专项的样本数。

## 保留的缺口与交付边界

E03 原完整场景仍缺证，真实模型语义均为 NOT_RUN，AC-10 未签整体 PASS。
完整 TASK-08、原任务自动续跑、前缀回放、副作用 exactly-once、生产可靠性收益均未作为本轮 Claim。
共享影响发现双向超时测试只断言后续作业结束，没有单独断言其成功；正文“队列继续”的成功证据
来自生命周期和 v2 子调用/存储恢复测试，不用该较弱断言替代。

本轮改动限定为本报告及运行证据归档。保留并排除用户 `CR02-CURRENT.md` 修改；
产品源码/既有测试未改，不重跑已成立门禁，不调用业务模型/收费探针，不读取凭据/Holdout，不推送。

## Astra 独立验收

实际通过 `collaboration.spawn_agent` 显式指定 `model=gpt-6-astra`、`reasoning_effort=xhigh`、
`fork_turns=none`，工具返回独立代理 `/root/resume_pair_astra`，并已收到其最终验收答复。
代理只读检查产品基线 `5d93e7b17bf65556f9c3e766472d9eb937c0f15e` 与正文 `PAIR-v1`；
验收后两条正文未改写。配置、逐项判定及答复文本转录见 [astra-review.json](evidence/CR02-runtime-2026-11-02/astra-review.json)。

| 验收对象 | Astra 判定 | 实质问题 |
| --- | --- | --- |
| 第一条：上下文构建与约束传递（C1/C2） | PASS | 无 |
| 第二条：受控执行与故障处理（R1–R4） | PASS | 无 |
| D1：恰好两条、贡献准确且内容互补 | PASS | 无 |

`blocking_findings=[]`，非阻断建议为无，无需限定复核。Astra 独立核对 11 个原日志节点、
上下文 3 项通过记录及 15 条 wire/落库投影，确认上述范围与缺口没有越界。
验收代理未执行测试或业务调用；不是执行者自评。
D2 的实际代理配置由主窗口核对，本地提交范围由主窗口在提交前后检查，固定 SHA 随最终交付提供。
