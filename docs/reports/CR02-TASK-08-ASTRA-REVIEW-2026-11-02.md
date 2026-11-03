# TASK-08：Astra 独立审查与限定复核

审查启动：2026-11-02；收口记录更新：2026-11-03（Asia/Shanghai）。审查基线：`a7b6f64291d0ffdb4d15f59af9c5c6ed96fb73d2` 上的 TASK-08 工作区差异。
实际代理：`/root/task08_astra_review`。通过 `collaboration.spawn_agent` 显式指定
`model=gpt-6-astra`、`reasoning_effort=xhigh`、`fork_turns=none`，收到独立初审和同代理限定复核答复。
审查全程只读，没有修改文件、执行测试、调用业务模型或扩大范围。

## 初审

总体 NEEDS_FIX；唯一阻断项为 **[P2] T08-F01：委派内部步骤及传递来源未校验各自前序**。

初审发现：普通 take 核对当前消费步骤的 predecessor，但 delegation 把原生 child 步骤收集为
components 时没有逐项核对；传递 receipt 只核对原 call/result，原始祖先前序损坏也可能被跳过。
仅修改已接受 child step.body.predecessor，正文/hash/父验收保持，旧候选仍可命中该委派单元。
该行为违反 T08-05/07 和原合同 C§6.4 的完整前序要求。

执行者随后实际运行单项负例复现，结果 **1 failed / 35 deselected / 1 warning，exit 1**：
期望 REPLAY_PREFIX_UNAVAILABLE，实际 error_code=None。
[修复前红灯日志](evidence/CR02-task08-2026-11-02/pytest-predecessor-red.log) 原样保留。
当时正在运行的旧候选全库已由测试代理终止，记录为 ABORTED，不作为通过门禁。

初审其余判定：T08-01/02/03/04/06/08/09、B 的模块边界/统一派发/状态重建 PASS；
T08-05/07 受 F01 阻断。新增简历数字及离线限定 PASS，但不能在代码阻断未关闭时正式升级。

## 修复与同轮限定复核

沿用原 steps、accepted/components、fresh 起点和 binding：

- history 支持指定本 step 之前的范围，source_step 在每一来源 job 重建并核对前序。
- 原生 child 与跨 attempt 来源均走该校验，绑定要求同 review/input 和严格更早 attempt。
- child receipt 回到原完整委派单元，核对 components、原完整 child 正文、稳定 ref 和新消费归属。
- 已接受 child 包库存与事件核对；缺失已接受包不能冒充自然未完成后缀。
- 没有新 Schema、兼容映射系统、通用 hash 链或第二套执行循环；fallback 不重置 deadline/计时起点/累计账。

修复后 **18 passed / 25 deselected / 1 warning，91.51s，exit 0**，覆盖原生 child 前序和
祖先 root/child 前序的两种 fallback、正常传递来源及原六组对照。
[修复后绿灯日志](evidence/CR02-task08-2026-11-02/pytest-predecessor-green.log) 已由 Astra 独立读取核对。

同代理最终答复：**T08-F01 CLOSED；本轮独立代码审查总体 PASS。**
`blocking_findings=[]`，无非阻断建议；T08-05/07 转为 PASS，其余已有 PASS 保持。
最终全库结果与提交范围由执行者另行核对，不以审查 PASS 代替测试门禁。

## 同轮简历 Claim 验收

第一条沿用已有上下文表述，本轮未发现破坏其依据。
第二条数字与限定 PASS：工具后故障 `3模型/1工具 → 2模型/0工具`，直接路线报告 payload 完全相同；
完整委派 `5/1 → 0/0`；父验收未保存 `5/1 → 5/1` 且 0 receipt。
Astra 核对同 seed DB 克隆、MockTransport 捕获请求/真实 HTTP 阻断、SnapshotTools 实际执行计数、
旧 call usage/预算条目不变断言，以及委派报告只规范化新 child_result_ref 的口径。
没有将这些结果外推为生产费用、Token 节省、语义准确率或独立个人主导。

原/修复后候选 build 与最终对照来源见 [证据索引](evidence/CR02-task08-2026-11-02/evidence-index.json)。
正式升级须同时具备最终全库通过；真实业务语义、E03、完整 TASK-09 仍保持各自未完成状态。

## 显式材料消费补充限定复核

后续窄核对发现：已显式授予的 source-backed RuleMaterial 原文和已投影 ObservationMaterial
可以被原生子结果合法引用，但回放只按“新工具 Source grants”覆盖 published_source_refs，造成误拒。
只读 code-scout 核对后实际补了两项负例：原生 child 已接受且 source_catalog 为空，重放却失败，
**2 failed / 43 deselected / 1 warning，18.37s，exit 1**，见[红灯](evidence/CR02-task08-2026-11-02/pytest-material-consumption-red.log)。

修复只在当前 specification 局部 deepcopy 出消费片段映射：加入当前显式 source-backed rule.body_ref
及与旧包实际已投影同 ID 观察完整一致的 initial observation.source_refs；排除 project_decision。
原 grants/SnapshotTools 不变，完整包、父验收、前序、build 和统一派发门禁全部保留。
**14 passed / 31 deselected / 1 warning，112.82s，exit 0**，包含两种材料消费、六组原对照及六项传递来源，
见[绿灯](evidence/CR02-task08-2026-11-02/pytest-material-consumption-green.log)。

同一个 `/root/task08_astra_review` 独立只读核对源码及准确绿灯节点，最终答复：
**材料消费误拒补充项 CLOSED；独立审查总体 PASS，blocking_findings=[]。**
原 F01、T08-01—09、B 边界与简历 Claim 的 PASS 结论保持，无新增问题或非阻断建议。
没有新 Schema/接口、工具扩权或第二轮整库审查；最终全库仍由执行者核对。

## 执行者最终门禁核对

2026-11-03 最终冻结候选已取得 **1683 passed / 0 failed / 3 skipped / 3 warnings，2110.23s，exit0**。
[最终日志](evidence/CR02-task08-2026-11-02/pytest-final-full.log) 与同次六份对照已归档，
Ruff全库check/format（296files）和差异检查通过。此处记录执行者/test-runner的实际门禁，
不声称审查代理运行了全库；原所有实质问题均已CLOSED，最终交付条件成立。
