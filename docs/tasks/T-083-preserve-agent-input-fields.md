# T-083 — 保留接收者输入字段（F1）

- 日期：2026-09-26；状态：FROZEN / approved-for-execution；前序提交4b98ec7。
- 授权：integration-audit-handoff-2026-09-26 的 F1，真实请求丢失后置字段已复现。

## Specification

### REQ-001 — 完整结构化输入

保留现有 receiver input Schema/validated_input 投影，仅序列化接收者已声明的输入。
每份上游 payload 完整 JSON 交付；不得截取整个 JSON 的前500字符或静默丢字段。
长 summary 后的 key_files/implementation_steps/risks/test_scenarios 必须进入实际接收请求。

### REQ-002 — 有界且显式失败

使用既有 TokenEstimator（4字符估算1token）估算完整 system+user messages，对照
policy.tokens.max_agent_input_tokens；超过预算时，在 LLM 调用前抛出安全 TOKEN_BUDGET_EXCEEDED。
不裁剪必要字段、不扩大全局限额。这个估计是上下文准入规则，不是 Provider 实际计费上界，
T-079 响应 usage 核算继续生效。AgentRunner 新增可选输入预算参数，默认沿用 DEFAULT_POLICY。

### AC-001 — 实际接收请求

真实 runner+AgentRunner+FakeProvider：Analyst 的700字符 summary 后 key_files 到达全部3个
Specialists；3个Specialists的长summary后关键字段到达 Synthesis；上下游接受与Handoff保持有效。

### AC-002 — 超限与隔离

合法但无法容纳的上游 payload 使下一阶段在实际发请求前退出3/TOKEN_BUDGET_EXCEEDED，Stage0仍保留；
receiver projection、DLP和原Adapter/请求预算回归通过。不能仅测试中间payload。

## Design

REQ-001：adapter 用完整紧凑 JSON 替换 _summarize_output；不改变 Schema 或 Prompt 的业务指令。
REQ-002：AgentRunner 构造时接收 max_input_tokens，runner 从当前policy传入；消息完整构造后进行
既有估算器的准入检查。错误使用SpecFlowError，直接经 scheduler/runner 政策路径保存。
允许：src/specflow/agents/adapter.py、src/specflow/runner_multi.py、
tests/test_agent_input_delivery.py、本规格/报告。无依赖、检索、模型参数、数据集或评分变更。

## Tasks

- [x] **TASK-001 — 请求级 RED→GREEN**：REQ-001、REQ-002，AC-001、AC-002；实际Fake请求与超限反例。
- [x] **TASK-002 — 验证交付**：REQ-001、REQ-002，AC-001、AC-002；Adapter、CLI、T078/T079回归；
  Ruff/diff、本地聚焦提交；最终五项全量统一收口。回退 git revert 本项提交。
