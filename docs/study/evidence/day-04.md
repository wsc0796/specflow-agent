# 第 04 天证据卡

- 状态：已收束（学习内容完成，ownership gate 为 partial）
- 日期：2026-09-09
- 路线：V5.3.1 Minimal Observability Patch，第 4 天
- 学习模式：SURVEY
- 本次来源：Day 4 主窗口学习过程与侧窗口概念澄清

> 本文件保留已经形成的学习结论与学习者可观察证据，不把聊天流水原样搬入。Day 4 已完成源码调查、Control Matrix v0 与强化反事实；最终矩阵由 Codex 协助修正，因此不能把整份矩阵标记为学习者独立闭卷产出。

## 今天的工程问题

当前 Evidence 路径如何收集、限制和传播仓库事实？路径安全控制为什么必须放在不可绕过的执行边界，而不能只依赖某一个上层调用者？

## 1. Evidence 主链的当前理解

```text
requirement
  → run_multi_agent
  → EvidenceCollector.collect
  → list_files / search_code / read_file
  → EvidenceBundle
  → serialized_context
  → final_dlp_scan
  → base_context.repository_evidence
  → validated_input
  → Repository Analyst 的 LLM user message
```

关键边界：

- `base_context` 中虽然存在 `repository_evidence`，但 `AgentRunner.execute` 优先读取 `validated_input`。
- `_validated_inputs` 只把原始 `repository_evidence` 放入 `repository_analyst` 的输入。
- 后续 Design、Test Strategy、Risk Review、Synthesis 和 Review Agent 接收经过 Schema 约束的前序 Agent 输出，不应表述为所有 Agent 都直接读取原始仓库证据。

源码位置：

- `src/specflow/runner_multi.py:60-112`
- `src/specflow/runner_multi.py:188-192`
- `src/specflow/runner_multi.py:552-636`
- `src/specflow/evidence/collector.py:42-148`
- `src/specflow/evidence/models.py:117-139`
- `src/specflow/agents/adapter.py:54-81`
- `src/specflow/agents/adapter.py:169-195`

## 2. EvidenceCollector 的依赖

这里的“依赖”不是指 `import`，而是指 `EvidenceCollector` 完成工作时需要由外部提供的对象或配置。

| 依赖 | 职责 | 不负责什么 |
| --- | --- | --- |
| `ToolExecutor` | 执行 Collector 构造的 `ToolCall` | 不决定整个证据收集顺序 |
| `repository_root` | 标识当前证据所属仓库，并进入 `EvidenceBundle` | 单独持有这个字段不等于完成路径安全控制 |
| `EvidenceCollectionConfig` | 限制关键词、调用次数、选中文件和证据字符等资源 | 不执行具体工具 |

构造器依赖与单次调用输入需要区分：

```text
构造器依赖：executor / repository_root / config
单次输入：run_id / requirement / project_summary / technology_stack
```

一句话解释：`EvidenceCollector` 负责流程编排，依赖 `ToolExecutor` 做实际工具执行，依赖 `config` 控制收集预算。

源码位置：`src/specflow/evidence/collector.py:21-49`。

## 3. 五层职责边界

```text
EvidenceCollector          流程编排者
    ↓
ToolExecutor               工具查找与执行调度者
    ↓
ReadFileTool               单次文件读取操作的实现者
    ↓
RepositoryAccessPolicy     仓库路径访问的确定性门卫
    ↓
文件系统                    真实数据源
```

| 组件 | 核心职责 |
| --- | --- |
| `EvidenceCollector` | 决定何时调用什么工具，整理匹配、摘录、哈希和调用记录，生成 `EvidenceBundle` |
| `ToolExecutor` | 根据 `tool_name` 从 Registry 取得工具，执行并把异常转换为失败结果，校验 Call/Result 对应关系 |
| `ReadFileTool` | 校验 `read_file` 专用参数，调用 Policy，执行受限 UTF-8 读取、内容脱敏与哈希计算 |
| `RepositoryAccessPolicy` | 规范化并解析路径，拒绝绝对路径、路径穿越、敏感路径、链接逃逸和仓库边界逃逸 |
| 文件系统 | 保存并返回真实文件字节，不理解 SpecFlow 的业务和权限规则 |

源码位置：

- `src/specflow/tools/executor.py:17-52`
- `src/specflow/tools/repository_tools.py:17-41`
- `src/specflow/tools/repository_tools.py:179-227`
- `src/specflow/tools/repository_policy.py:37-120`
- `src/specflow/tools/repository_policy.py:205-228`

## 4. `truncated` 与 `error_type`

### 4.1 `truncated` 的工程语义

`truncated=True` 表示工具成功返回了结果，但受到数量、字符或文件字节上限影响，只返回了一部分；它不等于工具失败。

```text
status = success + truncated = false → 成功且完整
status = success + truncated = true  → 成功但不完整
status = failed                       → 执行失败
```

Collector 会累计各阶段的截断状态：

```text
最终 truncated
= list_files 被截断
  或任意一次 search_code 被截断
  或 read_file / 总证据长度被截断
```

只要任意一步不完整，最终 `EvidenceBundle.truncated` 就保持为 `True`，不能被后续完整调用改回 `False`。

工程影响：如果搜索结果中没有发现权限校验，但 `truncated=True`，只能说“当前返回的证据中没有发现”，不能断言“整个仓库不存在”。

源码位置：

- `src/specflow/evidence/collector.py:58-85`
- `src/specflow/evidence/collector.py:93-130`
- `src/specflow/evidence/models.py:91-92`
- `src/specflow/evidence/models.py:133-138`
- `src/specflow/tools/repository_tools.py:80-90`
- `src/specflow/tools/repository_tools.py:125-175`

### 4.2 字段类型

```python
truncated: bool = False
error_type: str | None = None
```

- `truncated` 是布尔值，默认 `False`，回答“结果是否被截断”。
- `error_type` 可以是字符串或 `None`，默认 `None`，回答“失败时是什么错误类型”。
- `None` 表示没有错误类型，不等于空字符串。

## 5. 为什么路径检查不能只放在 EvidenceCollector

`ToolExecutor` 不要求调用者必须是 `EvidenceCollector`。其他代码也可以直接构造 `ToolCall` 并调用：

```python
executor.execute(call)
```

`ToolExecutor` 只根据工具名找到具体工具并执行；它不会验证调用者身份。如果路径检查只存在于 `EvidenceCollector`，任何绕过 Collector 的入口都会绕过该检查。

当前路径把检查放在更靠近文件系统的位置：

```text
任意调用者
  → ToolExecutor
  → ReadFileTool
  → RepositoryAccessPolicy.resolve_file
  → 文件系统
```

因此，绕过 Collector 直接调用 `read_file`，仍会执行 `RepositoryAccessPolicy`。这是一条路径访问不变量。

但不能把它扩大为完整权限结论：

- 它证明的是“这个路径是否允许读取”。
- 它不自动证明“这个 Agent 是否有权调用 `read_file`”。
- 它不自动证明所有生产代码都没有直接调用 `Path.open()` 等旁路。

## 6. AOP / Middleware 判断

当前结论：不使用 AOP 替代 `RepositoryAccessPolicy`。

AOP 或 Tool Middleware 更适合承载：

- Trace 与耗时；
- 通用 Budget；
- 通用 Schema；
- per-Agent Tool Permission；
- 通用 Retry 入口。

Policy 更适合承载：

- 仓库根目录约束；
- 绝对路径与 `..` 路径穿越拒绝；
- 敏感文件拒绝；
- 链接与 reparse point 检查；
- 最终真实路径是否仍位于仓库内。

原因：AOP 只能拦截经过代理、装饰器或切点的调用。直接实例化、绕过代理、自调用或新增入口忘记挂切面，都可能形成旁路。尤其在 Python 中，没有默认的 Spring 式容器代理保证。

推荐分层：

```text
调用者
  → 可选 ToolExecutor Middleware：Trace / Budget / 通用 Permission
  → ReadFileTool：专用参数校验
  → RepositoryAccessPolicy：不可绕过的路径 hard deny
  → 文件系统
```

## 7. 按 V5.3 / V5.3.1 修正后的结论

不能提前把当前设计称为“全局最优解”。更准确的表述是：

> 当前 `ReadFileTool → RepositoryAccessPolicy → 文件系统` 是合理的已实现路径安全基线；是否形成完整、最优的 Runtime Safety 仍是 `unknown`，必须通过 Control Coverage Audit 沿所有实际执行入口验证。

路线要求：

- 所有 LLM / Tool / Write 路径都要审计 Budget、Retry、Schema、Trace、Permission 和 DLP。
- 敏感、越权和明确禁止的操作必须由确定性代码 hard deny，模型无覆盖权。
- Runtime Middleware 是候选方案，不是当前学习任务。
- 只有 Control Coverage Audit 证明存在重复或漏控，并造成真实 correctness 问题，才考虑引入 Middleware；不能只为架构美感重构。

当前仍需验证、不能脑补的项目：

- 所有生产仓库读取入口是否均经过 Repository Tools；
- per-Agent tool permission 是否运行时强制生效；
- Evidence Tools 是否被 RuntimeGuard 覆盖；
- 通用 Schema、Retry、Trace 与 DLP 是否在所有入口一致执行。

路线依据：

- `docs/study/ROADMAP_V5_3_1.md`
- `D:\Downloads\AI_Agent工程化学习路线_最终执行版_V5.3_FINAL.docx`

## 8. AI 时代应该把代码学到什么程度

不应只看“功能已经实现”，也不需要逐行背诵所有语法。

```text
第一层：能说清模块解决什么问题，以及输入、处理、输出
第二层：看懂影响正确性、安全、失败和控制边界的关键代码
第三层：普通语法、局部变量和样板代码按需查询
```

本次 `truncated` 值得看懂，因为它改变下游对证据完整性的判断；`.get()`、`bool()` 的具体写法不需要死记。

是否掌握可用四个问题自检：

1. 不看代码，能否说清输入、处理和输出？
2. 能否指出执行控制位于哪个边界？
3. 能否给出一个失败或反例？
4. 能否回到源码、测试或 Artifact 证明判断？

## 9. 失败语义与高级反事实的价值

失败语义回答：系统出错、无证据或证据不完整时，应该继续、降级、失败还是安全停止。它用于防止“代码跑完但产生了无证据结论”的错误成功。

高级反事实回答：删除、替换或扩展组件后，哪些不变量会丢失。例如引入 LLM 自主选 Tool、Vector Retrieval、MCP 或 Middleware 后，路径边界、敏感文件 hard deny、Budget、Schema、DLP、合法终止和审计记录仍不能被绕过。

学习顺序：

```text
先看懂主链
  → 再定位六类控制
  → 再判断失败语义
  → 最后用反事实检验架构理解
```

“放到后续复盘”表示延后，不表示永久跳过。

## 10. 本侧窗口的学习者可观察证据

学习者已经独立完成以下判断：

- 当 `list_files` 完整而 `search_code` 被截断时，最终 `truncated=True`。
- `truncated=True` 表示“工具成功，但只返回部分结果”，不等于工具失败。
- 搜索结果被截断时，不能断言仓库中不存在某项实现。
- 原因能够压缩为：“搜索结果不完整。”
- 已识别 `ToolExecutor` 不要求调用者必须是 `EvidenceCollector`，并据此讨论安全校验应位于不可绕过边界。

这部分可作为 Day 4 learner-owned Explanation 的阶段性证据，但尚不能替代完整 Evidence 主链图和 Control Matrix v0。

## 11. 主窗口补充的学习者可观察证据

学习者在主窗口完成或经定向提示修正了以下判断：

- 独立给出 `requirement → EvidenceCollector → EvidenceBundle → serialized_context → base_context → validated_input → Agent user message` 主链，并附源码位置。
- 判断工具顺序由确定性程序固定，模型不参与当前 Evidence Tool 选择。
- 识别 `EvidenceExcerpt.excerpt` 直接来自 `search_code` 的 `match`，不是 `read_file.content`。
- 区分 `matched_files`、`selected_files` 与 `source_hashes` 的三个阶段，并识别 `source_hashes` 是 `path → content_hash`。
- 识别路径校验必须位于 `ReadFileTool → RepositoryAccessPolicy` 的不可绕过边界，而不能只依赖 `EvidenceCollector`。
- 识别 Runner 没有把 `policy.repository.max_file_bytes` 传入 `RepositoryToolSet`。
- 识别 Evidence Tools 没有接入 legacy Worker 使用的 `RetryStrategy(max_retries=1)`。
- 识别 `tool_permissions` 没有进入 `ToolExecutor.execute()` 的运行时授权判断。
- 识别 LLM 自主选择工具后，参数、路径、Budget 与 DLP 仍必须由模型外部的确定性代码执行。
- 识别零摘录路径需要在 Coordinator/Agent 前 fail-closed，并能用调用标志断言区分“退出码为 3”和“确实没有执行”。

需要保留的学习限制：

- `ToolCallRecord` 与具体代码摘录的区别经过多次定向提示后才建立。
- Control Matrix 初稿把 Budget 与 Retry 误标为“对”，最终状态由 Codex 给出并解释。
- 因此 Day 4 的主链 ownership 证据较强，Control Matrix ownership 仍为 partial；后续应通过闭卷复述重测，而不是把 AI 整理表直接当作本人掌握证明。

## 12. Control Matrix v0

| 控制 | 状态 | 已证明的当前事实 | 关键限制 | 源码锚点 |
| --- | --- | --- | --- | --- |
| Budget | `×` | Evidence 路径存在关键词、工具调用、选中文件和总证据字符等上限。 | Runner 只把部分配置传给 Collector；`policy.repository.max_file_bytes` 没有传入 `RepositoryToolSet`，不能宣称 Runner 限制完整作用到具体工具。 | `src/specflow/runner_multi.py:94-105`；`src/specflow/tools/repository_tools.py:20-30` |
| Retry | `×` | 单次 Evidence Tool 调用会记录成功或失败。 | 工具失败后返回 `None`，当前 Evidence 路径没有重试；`RetryStrategy(max_retries=1)` 接入的是 legacy Workers。 | `src/specflow/evidence/collector.py:150-191`；`src/specflow/runner.py:139-168` |
| Schema | `✓` | `ReadFileTool` 在运行时拒绝未知参数、空路径和非法路径。 | `ToolMetadata.input_model="ReadFileInput"` 只是字符串声明；没有证据证明该命名 Schema 被实例化执行。这里的 `✓` 只表示已实现工具专用运行时参数校验。 | `src/specflow/tools/repository_tools.py:196-200`；`src/specflow/tools/models.py:26-49` |
| Trace | `×` | `ToolCallRecord` 保存工具名、状态、参数/输出摘要、耗时、截断与错误类型；Agent 另有 `AgentTraceSpan`。 | 两套记录缺少共同的记录级 `run_id/span_id` 关联；当前只能依靠同一运行目录做粗粒度归组。 | `src/specflow/evidence/models.py:33-54`；`src/specflow/trace/models.py:47-92`；`src/specflow/runner_multi.py:499-507` |
| Permission | `✓` | Repository Tools 在工具内部执行仓库根目录、路径穿越、敏感路径与链接逃逸限制。 | 这里的 `✓` 只表示路径访问边界；`AgentIdentity.tool_permissions` 没有接入 `ToolExecutor`，不能宣称 per-Agent Tool Permission 已实现。 | `src/specflow/tools/repository_policy.py:106-120`；`src/specflow/tools/repository_policy.py:205-228`；`src/specflow/tools/executor.py:17-43` |
| DLP | `✓` | `search_code` 摘录、`read_file` 完整输出、Evidence 序列化与进入 Provider 前存在内容脱敏。 | 只能证明已知凭据模式受到处理，不能证明任意未知格式的秘密都不会泄露。 | `src/specflow/tools/repository_tools.py:152-159`；`src/specflow/tools/repository_tools.py:230-239`；`src/specflow/evidence/models.py:117-139`；`src/specflow/runner_multi.py:112` |

状态解释：矩阵中的符号针对表内明确口径，不代表整个系统在该控制维度“全局完成”。例如 Permission 的路径级 `✓` 不能覆盖 per-Agent permission；Schema 的手写参数校验 `✓` 不能覆盖声明式 Schema 执行。

## 13. 失败语义、测试强度与反事实

### 13.1 零摘录 fail-closed

`run_multi_agent` 在 `evidence.excerpts` 为空时持久化 `EVIDENCE_NOT_FOUND` 并返回 3，发生在 Coordinator 创建和 Agent 调度之前。对应测试不仅断言退出码，还断言：

```python
assert repository_analyst_called is False
assert coordinator_plan_called is False
assert manifest["stages_completed"] == 0
```

这组负向断言能排除“Coordinator 已经执行但最终仍返回 3”的错误实现。

源码与测试：

- `src/specflow/runner_multi.py:125-166`
- `tests/test_cli_multi_agent.py:74-131`

### 13.2 LLM 自主 Tool Loop 的控制边界

若未来把固定 Evidence 流程改成由 LLM 自主选择工具，模型只能提出 `tool_name + arguments`；以下控制仍必须保留在确定性代码层：

| 控制 | 不可绕过的边界 |
| --- | --- |
| 参数校验 | ToolCall 进入具体 Tool 之前 |
| 路径与敏感文件限制 | Tool 即将访问文件系统之前 |
| 调用次数与终止 | 包围整个 Tool Loop 的 Runtime |
| DLP | Tool 输出以及进入 Provider/Artifact 之前 |

其中当前 `EvidenceCollector._call_counter` 只约束固定 Collector；如果未来更换控制者，该 Budget 必须迁移到模型外部 Runtime，不能随 Collector 一起消失。

### 13.3 `read_file` 返回路径一致性

Collector 使用请求变量 `path` 写入 `source_hashes[path]`，但没有检查 `read_result["relative_path"] == path`。如果错误 Tool 对读取 `A.py` 的请求返回 `B.py` 的路径与哈希，Bundle 可能把 `A.py` 的搜索摘录与 `B.py` 的哈希错误配对，破坏 provenance。

当前内置 `ReadFileTool` 的返回路径来自 `RepositoryAccessPolicy`，因此该问题是契约完整性硬化候选，不应在没有可复现当前失败和任务规格时扩大为已利用的生产漏洞。

源码锚点：

- `src/specflow/evidence/collector.py:100-118`
- `src/specflow/tools/repository_tools.py:196-212`
- `src/specflow/tools/executor.py:45-52`

## 14. 候选改进点与处理时机

| 候选项 | 当前影响判断 | 建议时机 |
| --- | --- | --- |
| 对齐 Runner Repository Budget 与 RepositoryToolSet limits | 配置接线不完整，可能使非默认 Runner 限制未作用到具体工具。 | 后续有冻结任务规格时优先验证并修复。 |
| 为 Evidence Tools 定义 retry 语义 | 当前没有重试；并非所有路径、权限或 Schema 错误都适合重试。 | 先按错误分类和幂等性设计，不直接套用 Worker Retry。 |
| 执行声明式 Tool input schema | 当前存在手写参数校验，但元数据声明未成为运行时事实。 | 在 Tool Runtime Safety/Behavior Suite 阶段验证必要性。 |
| 关联 Evidence ToolCall 与统一 Trace | 不影响当前结果生成，但降低记录级故障定位能力。 | Day 22-23 Minimal Observability Slice。 |
| 强制 per-Agent Tool Permission | 当前 Agents 没有获得 ToolExecutor，直接暴露较低；字段仍可能造成错误能力声明。 | 引入自主 Tool Loop 前必须完成。 |
| 校验 `read_result.relative_path` 与请求路径一致 | 防止摘录与 source hash 错配。 | 先写可复现契约测试，再决定是否进入 Day 7 最小 Patch。 |

## 15. Day 4 完成结论

- Evidence 主链图：完成，含直接 Evidence 只进入 Repository Analyst 的边界。
- Control Matrix v0：完成并经源码核对；最终修正由 Codex 协助，ownership 为 partial。
- 失败语义强化：完成零摘录 fail-closed 与负向执行断言分析。
- 高级反事实：完成 LLM 自主工具控制边界与返回路径一致性分析。
- SpecFlow 产品代码修改：无。
- 测试执行：本轮未运行；引用的是现有测试源码，不冒充新的通过记录。
- 外部供体、依赖、Vector/Hybrid/Rerank：未进入。

## 16. 明早主动回忆题

1. 不看代码，画出 `requirement` 到 Repository Analyst LLM user message 的 Evidence 主链，并标出每次数据形态变化。
2. 为什么 `list_files` 返回的 `files` 没有直接决定 `matched_files`？当前 `matched_files` 从哪里产生？
3. 为什么 `ReadFileTool → RepositoryAccessPolicy` 是路径安全边界，而 `tool_permissions` 仍不能标成 per-Agent 运行时权限？
4. 如果 `run_multi_agent` 返回 3，为什么还不能据此证明 Coordinator 和 Agent 没有执行？
5. 如果未来由 LLM 自主选择 Tool，哪些控制必须保留在模型外部 Runtime，为什么？

<details>
<summary>参考答案（建议先闭卷回答，再展开核对）</summary>

### 1. Evidence 主链

```text
用户 requirement
  → run_multi_agent 校验输入并创建 run_id
  → 注册 Repository Tools，创建 ToolExecutor 与 EvidenceCollector
  → extract_keywords(requirement)
  → list_files：提供发现文件数量与截断状态；当前 Collector 不消费返回的 files 列表
  → search_code：按关键词返回 relative_path / line_number / excerpt / match_count
  → matched_files：所有搜索命中的文件路径
  → selected_files：按匹配度和路径相关性排序后，受 max_selected_files 限制的路径
  → read_file：对选中文件执行路径策略、有界读取、内容脱敏，并返回 content_hash / truncated
  → 读取成功后，将 search_code 的 match 转成 EvidenceExcerpt，并保存 path → content_hash
  → EvidenceBundle
  → serialized_context：把搜索词、匹配数量、摘录、截断与警告转换为文本
  → final_dlp_scan
  → base_context.repository_evidence
  → _validated_inputs：只有 Repository Analyst 直接获得原始 repository_evidence
  → AgentRunner._build_user_message
  → LLM user message 中的 Untrusted Repository Evidence
```

关键数据形态变化：

```text
requirement 字符串
→ ToolCall / ToolResult
→ match 字典
→ EvidenceExcerpt
→ EvidenceBundle
→ evidence_text
→ base_context
→ validated_input
→ LLMMessage
```

### 2. `list_files.files` 与 `matched_files`

`list_files` 返回 `files / count / truncated`，但当前 Collector 只读取 `count` 和 `truncated`，没有把 `files_output["files"]` 传给 `search_code`。`search_code` 自己遍历允许的 `.py` 文件并返回 `matches`；Collector 从每条 `match["relative_path"]` 构造 `matched_files`。

因此：

```text
list_files.files ≠ matched_files 的直接来源
matched_files ← search_result.matches[*].relative_path
```

### 3. 路径安全与 per-Agent Tool Permission

`ReadFileTool` 在真正访问文件系统前调用 `RepositoryAccessPolicy.resolve_file()`。因此，无论调用来自 EvidenceCollector、MCP、API 还是未来模块，只要经过 `read_file`，都会执行仓库根目录、路径穿越、敏感文件与链接逃逸检查。这是不可绕过的路径资源边界。

`AgentIdentity.tool_permissions` 目前只是身份字段；`ToolExecutor.execute()` 只接收 `ToolCall`，没有接收 `agent_id`、`AgentIdentity` 或 `tool_permissions`，所以不能据此声明 per-Agent Tool Permission 已被运行时强制执行。

### 4. 为什么退出码 3 不足以证明提前停止

`run_multi_agent` 的多个失败位置都会返回 3。即使错误实现先执行 `Coordinator.plan()`、之后再返回 3，`assert exit_code == 3` 仍会通过。

真正证明零证据路径停在执行前的是负向调用与阶段断言：

```python
assert repository_analyst_called is False
assert coordinator_plan_called is False
assert manifest["stages_completed"] == 0
```

它们分别证明 Repository Analyst 未执行、Coordinator 未规划，并且没有完成任何 Agent Stage。

### 5. LLM 自主 Tool Loop 中必须保留的确定性控制

模型可以提出下一步工具和参数，但以下控制不能只依赖 Prompt：

| 控制 | 应执行的确定性边界 |
| --- | --- |
| 工具白名单与 per-Agent Permission | ToolCall 进入执行器之前 |
| 参数与 Schema 校验 | ToolCall 进入具体 Tool 之前 |
| 路径、敏感文件与资源 hard deny | Tool 即将访问文件系统或外部资源之前 |
| Budget、最大迭代与终止 | 包围整个 Tool Loop 的 Runtime |
| Retry、幂等与副作用审批 | Runtime/Side-effect 执行边界；不可逆动作执行前 |
| DLP | Tool 输出以及进入 Provider、日志或 Artifact 之前 |
| ToolCall 审计与 Trace | Runtime 执行边界，使用可关联的 run/step/span 标识 |

原因：模型是动作提议者，也是 Prompt Injection、错误规划和循环失控的潜在来源；不能同时让它充当自己权限、预算和安全规则的最终裁判。

> 本参考答案由 Codex 整理，用于第二遍核对，不计作学习者独立闭卷证据。

</details>

## 17. 下一步与停止边界

- Day 4 到此停止，不在本日修改产品代码或继续扩题。
- Day 5 先建立 Context/State 总框架，再追长上下文、冲突证据、上下文污染与四类 State 边界。
- Day 5 初始仍使用 `SURVEY`：先给源码入口和问题地图，等待学习者明确开始后再逐题推进。
