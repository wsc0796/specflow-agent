# T-079 — Multi-Agent 请求预算与剩余时间边界

- 日期：2026-09-26；状态：FROZEN / IMPLEMENTED；批准依据保留如下；模式：BUGFIX。
- 授权：用户在只读核实后明确要求“把有必要修复的地方，给我修复”。不复用 T-078 的文件限制，
  本规格为新的必要修复范围；不重复请求实施批准。
- 基线：`633a941e3ff81a22282ea4fbd60576ac026f9956`；本地 checkout，分支 `codex/t079-llm-budget-boundary`。
- 既有学习材料、Word、Day14 越界记录与 raw attempts 保留；learner PARTIAL 不变。

## Specification

根因：runner 在 Agent executor 层统计一次调用和最终输出 usage，漏掉 Coordinator 的实际请求，
也漏掉收到响应但 JSON/Schema 失败的 usage；请求超时只使用静态配置上限，没有随剩余时间缩短。
旧 max_llm_calls=10 可以执行 6 enrichment + 6 Agent 共 12 次真实请求，与配置承诺矛盾。

### REQ-001 — 所有实际 LLM 请求统一准入

Coordinator 与 Agent 共享一次运行的调用/Token 预算，发送前原子检查调用数、已知输入消耗与
可用输出预算，给并行在途请求预留输出额度。每次实际 complete 计一次，确定性 Agent 不算 LLM。
调用上限默认仍为 10；显式上限不放宽。完整 12 请求的成功测试配置至少 12，不删验收断言。

### REQ-002 — 先计量再解析，缺失仍未知

响应 usage 在业务 JSON/Schema 解析前记录；超额响应的已观测用量也保留。
预算异常必须穿过 adapter/enricher 到 runner，不能作为普通降级被吞掉。
缺失/畸形 usage 或请求失败导致的未知消耗，阻止后续新请求；错误输出不得包含原正文或秘密。
失败 Artifact 记录已观测小计、已发请求数、响应 usage 覆盖与完整性，不把未知当 0。
不声称已发并行请求可撤回，也不声称能在没有 tokenizer/Provider 合同的情况下预知输入实际费用。

### REQ-003 — 按剩余时间执行

每次 LLM 请求前后检查共同 deadline；传入请求的 timeout 不超过当前剩余时间及 Provider 配置。
已经过期不发送，过期后返回的结果不进入已接受 stages。HTTP timeout 是 I/O 等待限额，不能冒充
整个运行的强制终止。保留 scheduler 等待已启动线程退出的合同；不新增线程强杀/取消 API/重试。

### REQ-004 — 保持既有安全与兼容边界

零 Evidence、Handoff integrity、T-078 审计、固定 topology、单轮 revision、Legacy 默认行为保持。
新增 request timeout 是可选字段，其他调用者默认行为不变；不新增依赖。Observer 必须观察实际
发送的请求参数。成功 run 总调用/Token 指标包含 Coordinator，agent_metrics 仍为分 Agent 视图。
只用 Fake/Mock/MockTransport，不读取正式 Holdout、不跑正式 Dev、不调用真实 Provider。

### AC-001 — 请求计数与并发准入

Fake 完整运行在 cap=12 时最多 12 次、指标为 12；cap=10 不发送第 11 次，低 cap 在 Coordinator
期间即保存 failed/exit=3。并发输出预留不能透支已知可用额度，失败后不能再准入新请求。

### AC-002 — 失败 usage 与传播

Fake 返回非法业务 JSON/Schema 时已观测 usage 仍在失败 Artifact；缺失/畸形 usage 显式失败。
政策错误不被 enrichment fallback 或 adapter provider 分类掩盖。Provider 异常本身保持原分类，
后续新请求因 usage 不完整停止。不得落盘正文或异常原文。

### AC-003 — 时间

可控时钟证明 timeout 随剩余时间减少、过期前阻止发送、响应后超时拒绝结果。
MockTransport 证明实际 HTTP timeout=min(配置,请求限额)，没有额外请求或重试。

### AC-004 — 回归与交付

新测试 RED→GREEN；相关回归、全量 pytest、Ruff/diff 通过。测试进程和已核对的临时 Mock worker
导入前清理 SPECFLOW_LLM_*，父/子真实 HTTP 哨兵均为 0。规格、报告、聚焦本地提交齐全；不推送。

### REQ-005 — Mock 基准的计量版本保持真实

全量暴露确定性 Mock benchmark 旧快照只含 Agent 计量，Token=0；新总计量正确包括 Coordinator，
为 input=3672/output=1800。旧 `benchmarks/results/mock-baseline.json` 保留原样，新增
`benchmarks/results/mock-baseline-request-budget-v1.json` 记录新版本，仅更新对应测试的比较路径。
不改变 12 条 Mock suite、评分器、任何正式 Dev/Holdout 或旧 baseline；不删除总量比较断言。

### AC-005 — 快照版本回归

现有 `test_benchmark_cli_writes_report_and_baseline` 仍完整比较 JSON，改为核对新快照；
旧快照逐字节不变。临时合成 worker 冷启动仍能正常导入并运行。

## Design

REQ-001、REQ-002：新增 `src/specflow/llm/budgeted.py`，一个运行共用 `LLMCallBudget` 和锁，
包装实际 client 并调用每个 receiver 的观察回调，使 observer 看见调整后的请求。复用 RuntimeGuard
既有阈值；新层管理在途输出预留、已观测 usage、未知调用与粘滞停止状态。释放预留不退还调用次数。
每次最多请求 min(调用方 max_tokens, 单次限额, 已知剩余输出/总量扣除预留)。输入不能预知，
响应后继续校验全部既有阈值；一旦不可计量或越界，新请求停止，已启动请求收口并记录结果。

REQ-003：`LLMRequest.timeout_seconds` 可选正有限数；OpenAI-compatible transport 取更小 timeout。
审查补充：同步 Observer 可能阻塞。预留调用/输出额度后执行观察回调，回调返回后在实际发送边界
再次检查 deadline 和粘滞失败，再计实际调用、刷新 timeout；未发送的请求必须释放预留且不计调用。
REQ-002、REQ-004：adapter 与 enricher 原样传播 SpecFlowError。runner 在 planning 阶段也收口政策失败，
Agent executor 包装仅保留时间检查，取消重复计费；统一失败 budget_usage 和成功总 metrics。
旧确定性 executor 无 Provider usage 属非 LLM 执行，不虚构调用数。

允许产品文件：`src/specflow/llm/budgeted.py`（新）、`src/specflow/llm/models.py`、
`src/specflow/llm/providers/openai_compatible.py`、`src/specflow/agents/adapter.py`、
`src/specflow/plan/enricher.py`、`src/specflow/runner_multi.py`。
允许测试：`tests/test_multi_agent_request_budget.py`（新）、`tests/test_cli_multi_agent.py`
（只有完整 Fake live 测试显式配置足额 cap，不弱化断言）。文档：本规格、对应报告。
RuntimeGuard/全局默认/调度器/Legacy/Evaluator/Prompt/数据集保持不改。
REQ-005 的必要验证扩展：新增上述版本化 Mock 快照，`tests/test_benchmark.py` 只改比较路径；
这由实际全量失败证明必要，不回写旧基准。adapter 的 SpecFlowError 同样在 execute 内导入，
避免 policy.models → plan.models → agents 包初始化的循环。

取舍：不以加大默认 cap 掩盖漏计；不使用 shutdown(wait=False) 伪造任务停止；不为精确预估
输入 token 新增 tokenizer。新字段可选，无数据库迁移；回退为本次聚焦提交的 git revert。

## Tasks

- [x] **TASK-001 — 冻结与 RED**：REQ-001、REQ-002、REQ-003、REQ-004；AC-001、AC-002、AC-003、AC-004；核对保护工作区，复用隔离包装；
  新增请求预算/usage/deadline 的 Fake、并发和 MockTransport 测试，观察预期失败。
- [x] **TASK-002 — 最小实现与 GREEN**：REQ-001、REQ-002、REQ-003、REQ-004；AC-001、AC-002、AC-003；按上述文件实现统一请求边界，
  focused pytest 通过，核对 Artifact 与真实观察请求的一致性。
- [x] **TASK-003 — 回归收口**：REQ-004，AC-004；相关回归、一次必要全量 pytest、Ruff/diff、代码审查，
  完成报告和逐路径本地提交。所有命令/失败/裁决记录于报告；不改旧学习原文。
- [x] **TASK-004 — 计量快照兼容**：REQ-005，AC-005；修复冷启动导入，保存新的 Mock 计量快照，
  重跑两条全量失败用例，再跑最终全量；旧快照不修改。
