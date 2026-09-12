# 第 03 天证据卡

- 状态：已完成
- 日期：2026-09-07
- 路线：V5.3.1 Minimal Observability Patch，第 3 天
- 学习模式：TUTOR

> Codex 可以代为完成机械性的源码搜索、命令执行和证据整理。Prediction、Verification、Interpretation、Trade-off 和 Explanation 必须由学习者本人完成。

## 今天的工程问题

开放式 ReAct Tool Loop 应在什么可观测条件下继续、成功停止或失败停止？它与 SpecFlow 的受控 Evidence/Tool 路径有什么区别？

## 学习者终止预测（执行前冻结）

> 当连续 3 轮 Observation 没有新增信息或重复相同结果，或者总轮数达到 5，循环应停止，并记录为失败终态，而不是伪装成成功

## 预测审查

- 该预测可验证，已通过。它给出了可观测的重复或无进展条件、明确阈值和失败终态分类。
- 数值 `3` 和 `5` 是后续有界实验需要验证的假设，不是通用的生产默认值。

## 当前证据边界

- 尚未执行第 3 天故障。
- 尚未公布实验结果。
- 尚未修改 SpecFlow 产品代码。
- 在限定的常用项目根目录中未找到本地 `agent-skeleton` 副本。随后，学习者指出了 GitHub 源码仓库 `wsc0796/agent-skeleton`。Codex 通过 GitHub API 对 commit `8f2d29e50c08a1786d3b5121008094b31dcfe4c3` 进行了只读检查，没有克隆仓库或安装依赖。

## 外部供体源码身份

- 仓库：`https://github.com/wsc0796/agent-skeleton`
- 默认分支：`main`
- 检查的 commit：`8f2d29e50c08a1786d3b5121008094b31dcfe4c3`
- 第 3 天源码文件：`src/core/agent_loop.py`、`src/core/tool_registry.py`
- 第 3 天测试文件：`tests/test_agent_loop.py`、`tests/test_tool_registry.py`
- 访问边界：仅通过 GitHub API 只读访问，没有创建本地副本、运行供体代码、安装依赖或修改供体。

## 下一道门

冻结开场预测后停止。下一轮只能继续 TUTOR，不得在同一轮进入 FAULT 或 PATCH。

## TUTOR 检查 1：工具成功与任务成功

### 场景

第一次 `search_code` 调用执行成功，但返回零条匹配。仍有其他关键词和工具可用，而且尚未出现重复 Observation。

### 学习者回答与纠正

- 初始分类：继续。
- 初始理由：没有命中结果，并且还有剩余轮次。
- 反例回答：为了维持规则而继续。
- 纠正：最大轮数是安全上限，不是必须消耗完的配额。仅有剩余预算不能证明应该继续。
- 学习者最终解释：“再继续进行，也仅仅是第一轮的重复”。

### 评估

- 已通过：如果已知下一次状态转换不会增加信息或改变状态，继续消耗轮次就不属于进展。
- 修正后的不变量：只有在合法的下一步可能改变状态或增加信息，并且没有触发安全或终止保护时，循环才能继续。
- 本次 TUTOR 检查没有执行故障。

## TUTOR 检查 2：最终答案信号与成功终止

### 场景

第 2 轮中，模型输出结构合法的断言“全部测试已经通过”，但 Trace 中没有测试命令或测试结果。当前仍有预算，而且存在一个能够取得缺失证据的安全测试工具。

### 学习者回答与纠正

- 初始分类：失败停止，因为 Trace 缺少测试证据。
- 第二次回答正确列出了剩余预算、安全工具和取得决定性新证据的可能性，但错误地把它们作为失败停止的条件。
- 纠正：这三个事实支持继续。只要仍有合法且有界的验证动作，证据暂时缺失就不是终态。
- 学习者最终解释：选择新的验证动作继续执行。只有没有预算、没有安全工具或无法取得决定性证据时，才失败停止。

### 评估

- 已通过：模型给出最终答案，并且输出通过 Schema 校验，仍不能证明任务已由证据支持并成功完成。
- 修正后的不变量：合法动作仍能取得必要证据时继续；验收证据已经存在时才能成功；证据缺失且不存在合法进展路径时，失败停止或安全弃答。
- 本次 TUTOR 检查没有执行故障。

## TUTOR 检查 3：Observation 安全回灌

### 供体源码事实

在本次检查的供体 commit 中，`ReActAgent.run` 会把完整的工具名称、参数和结果记录到 `AgentStep`，但面向模型的 Observation 只包含 `tool` 和 `result`。重复调用检测则单独使用工具名称与序列化参数作为键，并在第三次执行相同调用之前停止。

来源：`wsc0796/agent-skeleton@8f2d29e`，`src/core/agent_loop.py:168-205`。

### 场景

模型请求 `read_file(path=".env")`。策略层硬拒绝该请求，而且任务没有经过授权的替代路径。

### 学习者回答与纠正

- 正确识别了读取动作、拒绝结果，并指出不得返回 `.env` 内容。
- 初始循环状态描述的是反复读取。这是需要避免的不安全执行轨迹，不是合法状态。
- 学习者最终回答：终止 Agent 循环并返回任务失败终态。原因是任务的唯一目标需要读取被拒绝的 `.env`，不存在合法替代路径，该拒绝不可重试，且不得绕过权限。

### 评估

- 已通过：Observation 必须保留经过清理的待执行动作、拒绝结果、硬拒绝且不可重试的策略结论，以及对应的循环处置，同时不能暴露秘密内容。
- 修正后的不变量：模型不能把硬拒绝改写成重试、权限提升或成功。只有存在不同的已授权路径时才能继续，否则必须失败关闭。
- 本次 TUTOR 检查没有执行故障。

## 学习者 Tool Loop 状态机 v0：正常路径

```text
                          ┌───────────────────────────────────────────────────────────┐
                          │                                               [工具执行完成，观测写入上下文]
                          ↓                                                     │
用户请求进入上下文 → LLM 决策 ──[action_type=tool_call]→ 生成 ToolCall → Tool 执行 → Observation 回灌
                          │
                          └──[action_type=final]→ 最终答案／成功终态
```

### 评估

- 学习者本人绘制的正常路径图已通过。
- 图中包含 LLM 决策分支、工具执行路径、Observation 回边和最终答案出口。
- 下一版需要保留的边界：“工具执行完成”只表示已经产生 Observation，不代表工具或任务执行成功。
- v0 有意省略失败保护，本轮也没有执行故障。

## 学习者 Tool Loop 状态机 v1：源码支持的保护出口

```text
                          ┌───────────────────────────────────────────────────────────────────┐
                          │                                       [未达 max_iterations]        │
                          ↓                                                           │
用户请求进入上下文 → LLM 决策 ──[action_type=final]──→ 最终答案返回／任务成功尚未验证               │
                          │                                                             │
                          └─[action_type=tool_call]→ 生成 ToolCall → 重复调用校验        │
                                                  │                    │              │
                                                  │                    └─[≥2 次重复]→ 保护性停止（重复调用触发）
                                                  │                                 │
                                                  └─[既有相同 ToolCall 次数 < 2]→ Tool 执行 → Observation 回灌 → 最大迭代校验
                                                                                        │
                                                                                        └─[达到 max_iterations]→ 保护性停止（迭代耗尽触发）

【出口契约】三个出口都返回 AgentResult；final 返回、重复调用停止、迭代耗尽停止之间，没有显式 status 或 terminal_reason 进行结构化区分。
```

### 评估

- 学习者本人绘制的状态机 v1 已根据 `wsc0796/agent-skeleton@8f2d29e` 验收通过。
- 重复调用分支会允许前两次相同调用，并在第三次相同调用执行前停止。
- 最大迭代分支使用配置项 `max_iterations`，没有把供体默认值 8 与学习者提出的假设值 5 混为一谈。
- 最终答案分支已经明确标注：循环会返回，但任务尚未被证明成功。
- 共用的 `AgentResult` 契约以及缺失 `status`、`terminal_reason` 分类的问题已经明确。
- 生成 v1 的过程中没有执行故障。

## 机械对照：开放式 ReAct Tool Loop 与 SpecFlow Evidence/Tool 路径

> 下表由 Codex 通过机械性源码检查整理。它属于源码证据，不属于学习者的 Interpretation 或 Trade-off 判断。

| 维度 | `agent-skeleton@8f2d29e` | SpecFlow `c0721ba` |
| --- | --- | --- |
| 控制者 | LLM 每轮返回 `action_type=tool_call`，并选择工具名称和参数。 | `EvidenceCollector` 依次调用 `list_files`，使用提取出的关键词循环调用 `search_code`，对文件排序后再调用 `read_file`。 |
| 循环结构 | LLM → 工具 → 面向模型的 Observation → LLM。工具选择和调用顺序可以根据每次 Observation 改变。 | 仓库工具在 Coordinator 和各 Agent 之前执行。Agent 接收序列化后的 Evidence 块，这条路径中不存在由模型驱动的 Tool/Observation 循环。 |
| 工具契约 | `ToolSpec` 使用 Pydantic 模型验证参数，然后调用已注册函数。 | `ToolCall` 和 `ToolResult` 是显式契约。`ToolExecutor` 每次只执行一个已注册工具，并校验结果身份和状态。 |
| 面向模型的反馈 | Observation 只包含 `tool` 和 `result`。详细工具参数保存在 `AgentStep` 中，不会进入面向模型的 Observation。 | `EvidenceBundle.serialized_context()` 包含经过清理的摘录、搜索词、数量、截断信息和警告。工具调用记录另行序列化用于审计，不会回灌给模型用于动态选择工具。 |
| 安全边界 | 已实现已注册工具查询、Pydantic 参数验证、重复调用保护、最大迭代保护和工具内部控制。内置文件工具会阻止绝对路径、路径穿越和敏感文件名。项目文档明确说明，目前没有按调用者授权，也没有工具权限模型。 | 仓库工具执行有界的只读路径和敏感文件策略。Evidence 在进入 Agent 前受数量限制并经过 DLP 扫描。每个 Agent 的 `tool_permissions` 是否在运行时执行仍记录为 UNKNOWN，本表不将其写成已实现事实。 |
| 无证据行为 | 工具结果作为 Observation 返回，LLM 可以继续选择其他动作，直到触发 `final` 或保护性返回。 | 可用摘录为零时，在 Coordinator 和 Agent 执行前以 `EVIDENCE_NOT_FOUND` 停止。 |
| 终止 | `final`、LLM 异常、重复的相同调用或迭代耗尽都会返回 `AgentResult`，但结果契约缺少结构化的 `status` 和 `terminal_reason`。 | 工作流具有显式的 `completed` 和 `failed` 状态，无证据与运行时策略失败也会分类记录。有界 Revision 不是通用 ReAct Tool Loop。 |
| 灵活性 | 同一次运行中，后续工具选择可以根据之前的 Observation 改变。 | Evidence 收集算法中的工具顺序和选择是确定性的。改变行为需要修改代码或配置，而不是依赖下一次 LLM 决策。 |

### 源码锚点

- 供体循环和 Observation：`wsc0796/agent-skeleton@8f2d29e`，`src/core/agent_loop.py:86-220`。
- 供体工具验证：`src/core/tool_registry.py:8-27`。
- 供体文件工具内部策略：`src/tools/builtin/__init__.py` 和 `tests/test_builtin_security.py`。
- SpecFlow 的确定性工具顺序：`src/specflow/evidence/collector.py:42-158`。
- SpecFlow 面向模型的 Evidence 序列化：`src/specflow/evidence/models.py:117-139`。
- SpecFlow 单独保存的工具审计记录：`src/specflow/evidence/models.py:141-178`。
- SpecFlow 无证据门：`src/specflow/runner_multi.py:87-137`。
- SpecFlow 显式工作流状态：`src/specflow/coordinator/state_machine.py:11-52`。

### 学习者 Interpretation 与 Trade-off

- 选择：有边界的混合方案。
- 收益：在安全边界内让 Agent 自主选择下一步，减少人工逐步控制，并提高对未知情况的适应性。
- 代价：执行轨迹更不确定，可能走错方向、浪费调用，并增加测试和审计难度。
- 审查状态：通过。
- 设计边界：确定性外层继续负责工具白名单、参数和路径校验、权限、预算、终止以及成功证据门；LLM 只能在允许的只读动作集合内根据 Observation 选择下一步。
- 本次 TUTOR 轮次没有执行故障。

## DeepSeek Harness 运行轨迹参考

> 本节由 Codex 根据官方仓库做只读机械检查，用于确定故障轨迹应保留哪些事实，不把 DeepSeek Harness 扩展为新的实现主线。

### 来源身份

- 官方仓库：`https://github.com/deepseek-ai/deepseek-harness`
- 默认分支：`master`
- 检查的 commit：`c389f96bf3a9b6807cb71ed6bdad5849be0df6d8`
- 访问方式：GitHub API 只读，没有克隆、安装或运行 DeepSeek Harness。

### Trajectory 能看到什么

- 按轮次组织的 SYSTEM、USER、ASSISTANT、TOOL、SUBTOOL、CONTEXT 和 COMPACTED 记录。
- Assistant 的输入、输出、已记录的 reasoning、TTFT、完成时间和 Token 用量。
- Tool 的调用标识、名称、参数、调用时 Schema、结果、错误状态、开始时间和耗时。
- Request header、压缩请求、会话结束、轮次结束以及 `error`、`errorCode`。
- sequence、duration、time、actual 四种时间线投影，以及按消息和工具划分的泳道。
- 详情面板中的 Summary、Payload、Result、Schema 和 Timing。

### 证据边界

- `ui-trajectory` 是持久 Session 事件的纯消费视图，不修改 Chat 会话，也不向模型注入内容。
- 它展示运行时已经记录并投影出来的模型、工具和会话事件。根据该边界推断，它不能证明或展示模型没有输出、运行时也没有记录的内部神经过程。
- reasoning 只有在来源事件包含对应内容时才能显示，不能把 Trajectory 视图等同于完整且可信的隐藏思维链。

### Day 3 故障轨迹采用字段

- 轮次或请求编号。
- Assistant 决策或可见 reasoning。
- Tool 名称、经过清理的参数和调用标识。
- Tool 结果、错误类型和是否允许重试。
- Observation 回灌内容。
- 开始时间、耗时和可用 Token 记录。
- 最终返回原因，以及成功、失败或保护性停止的分类是否明确。

### 源码锚点

- `packages/client/ui-trajectory/README.zh.md`
- `packages/client/ui-trajectory/src/client/trajectory-contract.ts`
- `packages/client/ui-trajectory/src/client/trajectory-record.ts`
- `packages/client/ui-trajectory/src/client/trajectory-event-projection.ts`
- `packages/client/ui-trajectory/src/client/timeline.ts`
- `snapshots/web/navigation-panes/trajectory.expected.md`

## FAULT F1：重复的相同 ToolCall

### 冻结环境

- 供体：`wsc0796/agent-skeleton`
- commit：`8f2d29e50c08a1786d3b5121008094b31dcfe4c3`
- 既有测试：`tests/test_agent_loop.py::TestReActAgent::test_agent_stops_on_repeated_calls`
- 既有 CI：GitHub Actions run `28861986729`
- CI 命令：Python 3.12、`ruff check .`、`pytest -v`
- 访问边界：只读检查既有源码、测试和 CI 日志，不克隆、不安装、不触发新的远程运行。

### 故障触发器

Mock LLM 在每一轮都返回完全相同的 ToolCall：工具为 `echo`，参数为 `{"message":"test"}`。该测试中的 `max_iterations=5`。

### 合法终态

- 保护性停止：重复调用保护在最大迭代数之前终止循环。
- 保护性停止：若重复保护未生效，则达到最大迭代数后终止。
- 不允许把任何一种保护性停止记录成已经完成用户任务的成功终态。

### 观察点

- LLM 决策轮数。
- 实际执行的 ToolCall 次数。
- 实际生成的 Observation 数量。
- `steps` 和 `tools_called` 的内容或数量。
- `AgentResult.answer`。
- 是否存在结构化 `status` 或 `terminal_reason`。
- CI 中对应测试的执行结果。

### 学习者 F1 Prediction

- 学习者预测：第 3 轮不会真正执行 `echo("test")`，也不会产生第 3 条 Observation。原因是相同命令已经执行两次，重复保护会在第三次工具执行前停止。
- 状态：已冻结，早于对应 CI 日志读取和实际轨迹公开。

### AI 机械执行证据

#### CI 直接观察

- GitHub Actions run：`28861986729`
- URL：`https://github.com/wsc0796/agent-skeleton/actions/runs/28861986729`
- head SHA：`8f2d29e50c08a1786d3b5121008094b31dcfe4c3`
- Job：`test`，结论为 `success`。
- `Run ruff`：成功。
- `Run tests`：成功。
- `tests/test_agent_loop.py::TestReActAgent::test_agent_stops_on_repeated_calls`：`PASSED`。
- 测试汇总：`44 passed, 1 warning in 2.08s`。

#### 源码推导轨迹

> CI 日志只显示测试通过，没有打印每轮 `AgentResult`、`steps` 或 Observation。下表根据固定 commit 的确定性 Mock 测试和 `ReActAgent.run` 控制流推导，不标记为 CI 直接 Trace。

| 轮次 | 相同调用的既有次数 | 是否执行 `echo("test")` | 是否产生 Observation | 结果 |
| ---: | ---: | --- | --- | --- |
| 1 | 0 | 是 | 是，第 1 条 | 写入 `call_history`、`tools_called` 和 `steps` 后回到下一轮。 |
| 2 | 1 | 是 | 是，第 2 条 | 再次写入记录并回到下一轮。 |
| 3 | 2 | 否 | 否 | 命中 `call_history.count(call_key) >= 2`，在 Tool 执行前返回。 |

由源码可确定的返回内容：

- `iterations=3`
- `len(steps)=2`
- `tools_called=["echo", "echo"]`
- `answer="Detected repeated tool calls. Stopping to avoid infinite loop."`
- `AgentResult` 没有 `status` 或 `terminal_reason` 字段。

源码锚点：

- `src/core/agent_loop.py:13-30`
- `src/core/agent_loop.py:148-205`
- `tests/test_agent_loop.py:73-82`

### 学习者 Verification

- 学习者判断：实际情况与预测一致。
- 学习者轨迹证据：第 3 轮发现命令已经重复两次，因此在工具执行前直接停止；总共只产生 2 个工具结果。
- 审查状态：通过。该回答引用了实际轨迹，而不是只复述预期规则。

### 学习者 Interpretation 与故障 Trade-off

- Interpretation：重复执行只会浪费时间和精力，仍然无法得到有效内容。
- Interpretation 审查：通过。该结论没有夸大为无限重试或系统宕机，也没有直接复制 Codex 的术语化示例。
- Trade-off 学习者判断：收益是节省 Token；代价是可能把合法的重复工具查询误判为无效重复，从而错过结果变化后的最佳状态。
- Trade-off 审查：通过。具体反例是状态轮询，前两次结果为 `running`，第三次原本可能返回 `completed`，但仅按工具名称和参数去重会提前拦截。
- 本轮不提出修复，也不修改供体或 SpecFlow 产品代码。

### F1 完成判断

- Prediction：完成。
- CI 与源码轨迹证据：完成。
- Verification：完成。
- Interpretation：完成。
- Trade-off：完成。
- 修复：不在 Day 3 范围内。
- 硬交付物状态：1 个可复现故障已完成。

## REVIEW：闭卷 Explanation

### 问题 1：开放 Tool Loop 的三类状态

- 第一次闭卷回答：
  1. 继续条件：“得到的结论是有效的”。
  2. 成功条件：“重复使用 Tool，由规则规定次数后得到量变到质变的结论”。
  3. 失败条件：“重复使用 Tool 且结论重复，浪费 Token 和时间”。
- 审查结果：未通过。第一项实际描述了成功候选；第二项错误地把重复次数当成成功证据；第三项识别了无进展，但没有覆盖证据缺失且无合法下一步等失败条件。
- 补救策略：每次只修正一个状态，先从“继续”开始。
- 补救 1，继续条件：通过。学习者说明，虽然当前没有测试证据，但仍有剩余时间和安全测试工具，可以继续取得证据。
- 补救 2，成功条件：通过。学习者说明，测试已经实际运行并成功，Trace 也保存了命令和结果，因此用户的唯一目标已有证据支持。
- 补救 3，失败条件：通过。学习者说明，请求没有通过安全策略。结合题设中的硬拒绝和无合法替代路径，任务必须失败停止。
- 状态：问题 1 经三项补救后通过。
- 限制：不得查看证据卡，不要求记忆字段名。

### 问题 2：两条路径由谁决定下一步工具

- 学习者回答：`agent-skeleton` 由模型决定选择什么，由代码负责能不能执行；SpecFlow Evidence 路径由代码预先固定工具流程。
- 审查结果：通过。模型拥有动作提议权，代码保留执行约束；SpecFlow Evidence 的工具顺序由确定性代码控制。
- 状态：完成。
- 限制：只比较控制者，不要求记忆类名或文件名。

### 问题 3：没有找到证据时如何处理

- 学习者回答：`agent-skeleton` 可以继续重试，由模型更换关键词、参数或工具；SpecFlow 在全部 Evidence 为空时停止。
- 审查结果：通过。一次空 Observation 不是开放循环的必然终态；SpecFlow 则在整个 Evidence 收集为空后，于 Agent 执行前失败停止。
- 状态：完成。
- 限制：只判断“继续尝试”或“执行 Agent 前停止”，不要求记忆错误码。

### 最终闭卷复述

- 学习者已完成一次整合复述，包含 Observation 回灌、ToolCall/JSON/未知工具继续分支、重复调用/最大迭代/LLM 异常停止分支，以及“开放循环由模型选动作、SpecFlow 由流程控制”的核心对照。
- 已通过部分：循环主干、继续条件、保护性停止、控制权对照。
- 待修正部分：学习者把 `action_type="final"` 直接称为成功停止。源码只能证明此时返回 `AgentResult`，不能证明任务事实、验收条件或业务结果已经成功；`AgentResult` 也没有显式 `status` 或 `terminal_reason`。
- 最终修正：学习者说明，模型输出 `final` 只能证明循环返回；对于测试任务，真正成功还需要测试证据。更一般地说，成功需要与任务验收条件对应的证据。
- 审查结果：经一次整合复述和一次定向修正后通过。
- 状态：完成。
- 要求：不用字段名，用 3 至 5 句话同时说明开放 Tool Loop 如何循环、何时停止，以及它与 SpecFlow Evidence 路径的核心差别。

## 第 3 天完成摘要

- 硬交付物 1：学习者 Tool Loop 状态机 v1，完成。
- 硬交付物 2：重复的相同 ToolCall 故障 F1，完成。
- 供体源码：`wsc0796/agent-skeleton@8f2d29e`，通过 GitHub API 只读检查。
- 故障执行证据：GitHub Actions run `28861986729`，对应测试为 `PASSED`，整套测试为 `44 passed, 1 warning in 2.08s`。
- 轨迹证据：CI 直接观察与源码推导轨迹已经分层记录。
- 对照结论：开放 Tool Loop 由模型提出下一步动作，代码保留执行约束；SpecFlow Evidence 路径由确定性代码控制工具顺序。
- 学习者设计选择：有边界的混合方案。模型只在允许的只读动作集合内自主选择，外层代码保留权限、预算、终止和成功证据门。
- 轨迹参考：只读检查 `deepseek-ai/deepseek-harness@c389f96` 的 Trajectory 视图，没有接入或运行该系统。
- Prediction、Verification、Interpretation、Trade-off 和闭卷 Explanation：完成。
- SpecFlow 产品代码修改：无。
- 供体修改、克隆或依赖安装：无。

## 已知限制

- 没有创建供体本地副本，因此逐轮细节来自固定源码与确定性 Mock 测试推导，不冒充 CI 直接输出的完整运行 Trace。
- 供体 `AgentResult` 缺少显式 `status` 和 `terminal_reason`，不能从结构上区分最终答案返回与保护性停止。
- `action_type="final"` 只能证明循环返回，不能证明任务事实或验收条件已经满足。
- 学习者提出的 3 轮无进展和总计 5 轮是实验假设，不是供体默认值或通用生产结论。
- DeepSeek Harness 仅用于参考轨迹字段。它展示运行时已记录事件，不证明模型未输出的内部神经过程。

## 下一步

停止在第 3 天。只有收到明确授权后，才能进入第 4 天。
