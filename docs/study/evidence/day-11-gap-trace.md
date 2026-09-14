# Day 11 Multi-Agent 只读 Gap Trace

- 日期：2026-09-14；启动源码：`271d409cb0164ffa998a47b164abed3682c60801`。
- evidence_state：`static-only`；AI-authored，不计 learner ownership。
- 读取范围：当前 Multi-Agent runner、Coordinator/enricher、AgentRunner、Provider、evaluation harness、
  metrics/validator 与相关测试；未读取 Holdout 题面，未调用 Provider 或正式 Dev。

## 1. 真实输入与 Context 接线

`run_multi_agent` 接收 repo、requirement、output、provider/model、policy。EvidenceCollector 当前使用
`max_selected_files=min(10, policy.repository.max_selected_files)`、
`max_total_evidence_chars=policy.repository.max_total_evidence_chars`、`max_tool_calls=20`。
序列化 Evidence 经 final DLP 后进入 `base_context.repository_evidence`。

`_validated_inputs` 只给 Repository Analyst `{requirement, repository_evidence}`；Design/Test/Risk 只收
requirement + repository analysis；Synthesis 只收三个 specialist output；Review 只收 synthesis output。
`AgentRunner._build_user_message` 才把 validated_input 投影进实际消息。因此 Multi-Agent 的原始仓库
Evidence 预期只在 Repository Analyst 请求可见，不能把 `base_context` 存在误写成所有 Agent 可见。

## 2. 请求、Prompt 与 Provider 观察缺口

- Coordinator 每个固定 Agent 调一次 `SemanticPlanEnricher._enrich_one`：user-only、temperature 0、
  max_tokens 1024、response_format json。失败按 agent 降级，不重试。
- 实际 Agent 使用 `AgentRunner`：system prompt 为角色/描述，user prompt 来自 `_build_user_message`，
  temperature 0、max_tokens=policy.tokens.max_agent_output_tokens（当前 3000）、response_format json、
  max_retries 默认 0。
- `OpenAICompatibleLLMClient.complete` 每次只发送一次同步 HTTP 请求，没有内部 retry。
- 当前 `run_multi_agent` 没有 request observer；manifest/metrics/traces 不能重建实际
  `LLMRequest.messages`。T-076 只补默认关闭、非干扰的观察面。

## 3. Budget、usage 与终态

`RuntimeGuard.consume_llm_call` 位于 Agent executor 外层；Coordinator 的 6 次 enrichment 请求不进入
该计数。`metrics.json` 又只从 stage agent results 聚合 usage，因此不含 enrichment usage。
即使 6 个 Agent usage 全部存在，也不能把 metrics total 当全部 Provider calls 的完整成本。

AgentRunner provider retry 为 0；enricher 无 retry；Provider 无 retry。Review REJECT 最多触发一次
revision，并产生目标 Agent + Synthesis + Review 三次额外 Agent 调用。产品合法返回主要为 0/2/3；
workflow 可 completed/failed，completed 与 Schema 通过仍不等于 task success。

## 4. Artifact/report profile

成功路径写 checkpoints、manifest、agent-outputs、handoffs、traces、sources、metrics，另写完整性清单
和 `_COMPLETE`。失败路径的 artifact 集可能更小。旧 `portfolio_multi_agent_mock@5f2815d` 要求七件、
completed、schema_unvalidated=0、schema_validated=6；它是 Mock portfolio profile，不能静默扩成
Dataset v1 live task_success 或通用 contract。T-076 报告 raw artifact observation，并让不适用的
contract_run_success 保持 unknown/N/A。

## 5. 公平性差异

Legacy 实际选文件上限 5；Multi-Agent 当前为 10。公共 Policy JSON 相同不等于 effective limit 相同。
原样运行忠实测当前产品路径，但 Evidence/Context 和所有下游质量/风险结果受混杂；统一为 5 则改变
Day 11 的“当前版本原样”对象，并需要独立 task spec/PATCH。两种实验不能静默互换。

## 6. 处置

T-076 只补 Dataset v1 Multi-Agent adapter、request observation、attempt journal、输入隔离、运行门和
报告骨架。完整 Token ledger、新通用 Evaluator、Prompt/限额/Context 修复均不在范围。正式 20 Dev
保持 0 attempted，直到学习者作公平性判断。
