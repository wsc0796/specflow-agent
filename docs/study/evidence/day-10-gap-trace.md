# Day 10 只读 Gap Trace

- 日期：2026-09-14；项目：`D:\Documents\ChatGPT\一个月冲刺\specflow-agent`。
- 源码快照：`cb665b4357d5b39498c5ac4a2bdd05d86affceb5`。
- 目标仓库/Gold revision：`08e5a66f8ea8216433c72744adab92aa07d99c45`。
- evidence_state：`static-only`；AI-authored，不计 learner ownership。
- `git diff --name-only 08e5a66f8ea8216433c72744adab92aa07d99c45 HEAD -- src tests pyproject.toml uv.lock`
  无输出，相关源码、测试、依赖文件与 Gold revision 相同。
- 未调用产品 runner、Provider、Dev baseline 或 Holdout；未读取 Holdout 题面。

## 1. 数据与旧入口的实际差异

已解析读取 `datasets/v1/dev.json` 全文件：顶层含 cases 数组，20 个 SF-RT-D ID，
类别为 5/5/4/3/3；包含 requirement、answerability、事实 Gold、expected_properties、
forbidden_claims、legal_terminal_state、annotation 等字段。合法终态中的 product_state_mapping
仍为 unknown，不能按题目类别预造产品终态。D018–D020 是题设安全请求，不创建真实敏感目标。

已解析读取 `calibration/v1/fixtures.json` 全文件：34 个独立 fixture，7 类 evaluator，
8 个 existing_core_only、26 个 contract-only 或 wrapper unknown。未执行 fixtures。
CAL-CR-N01 明确七件/六 Schema profile 对 Legacy 十件 artifact 为 N/A；
CAL-FR 保留比例和计数、不定义任务通过线；CAL-TC-U01 保留 unknown coverage/full_total。

| Gap | 源码与测试证据 | 对 Day 10 的影响 |
| --- | --- | --- |
| G1：portfolio suite 硬编码 | `src/specflow/evaluation/benchmark.py:44` load_benchmark_cases；`:65` 固定 12；`:70` 固定 4/4/4；`tests/test_benchmark.py:19` | 不可把新 Dev 塞入旧入口或修改 12 为 20 后沿用报告 |
| G2：portfolio 执行路径不对 | `benchmark.py:81` run_mock_benchmark；`:105` 调 run_multi_agent(mock=True)；`src/specflow/cli.py:16` | 会执行 Day 11 范围的路径，且只证明 Mock contract |
| G3：旧 Legacy loader 格式不符 | `src/specflow/evaluation/runner.py:20` 遍历所有 *.json；`models.py:29` EvaluationCase 要求 title/repository_type/expected_* 等；`tests/test_evaluation.py:55` | 新文件是一个 suite envelope；glob 新目录还可能打开 Holdout，绝不能尝试 |
| G4：旧运行/评分绑定 | `evaluation/runner.py:47` run_mock_evaluation；`:63` 固定 mock/max_files=8，expected_file_patterns 缺失则先跳过产品 | 新 Dev 需要独立运行清单，不能用 Gold 决定哪些题允许执行 |
| G5：旧 A/B 非语义 scorer | `evaluation/multi_agent_runner.py:56` 同时跑两路径；`:73`/`:83` requirement_coverage=0 | 不执行该入口，不能从固定占位分推导任务效果 |

对 `src/ tests/ scripts/` 定向搜索 dataset_version、answerability、gold_evidence、expected_properties
无匹配（rg 退出码 1 表示无匹配）。结论限定为这些当前执行面：未发现新 Dataset 接线；
不把学习文档或 Day 9 数据检查程序当产品 loader。

## 2. 输入隔离有两条通道

1. 参数通道：产品只接收 requirement + 授权 repo + 正常运行配置；完整 Case 留在 Evaluator。
2. 仓库通道：`manifest.json` 的 input_isolation.repository_snapshot_rule 要求排除题库、Gold、
   calibration 与答案笔记，不能扫描 authoring checkout。

`src/specflow/tools/repository_policy.py:40` 的 ignored_directory_names 没有 docs/study；
`:134` 开始目录遍历。不能依靠现有敏感文件过滤来保证评测数据隔离。
只固定到 08e5a66 也不等于自动排除了更早学习笔记；需要预声明、两拓扑共用的目标快照范围。
冻结内容 bf77d19 是 Dataset 身份；08e5a66 是被读源码身份；运行 harness 的 commit 是第三个身份。

## 3. Legacy Context 接线缺口（静态证据）

| 观察位置 | 实际字段/行为 |
| --- | --- |
| `src/specflow/evidence/collector.py:89`、`:111`、`:120` | 选文件、建立摘录、总字符预算裁剪 |
| `src/specflow/evidence/models.py:117` | serialized_context 序列化保留的摘录 |
| `src/specflow/runner.py:148`、`:186`、`:193` | final_dlp_scan 后传入 WorkerContext.project_context |
| `src/specflow/runner.py:115` | 另建 ProjectContext，仅项目元数据；technology_evidence=[] |
| `src/specflow/workers/analyze.py:201` | builder 使用 self._project_context 与 context.requirement |
| `src/specflow/workers/generate.py:217` | builder 使用 self._project_context、requirement、analysis 输出 |
| `src/specflow/workers/review.py:256` | builder 使用 self._project_context、requirement、analysis/generation 输出 |
| `src/specflow/context_builder/builder.py:45` | 序列化传入的 ProjectContext 对象 |
| `src/specflow/workers/analyze.py:218`；generate.py:235；review.py:277 | budget 后的 system/user messages 才交 LLMClient.complete |

三个 execute 路径均未使用 `context.project_context`；传入 WorkerContext 的 Evidence 摘录
未按这条字段接线进入构造请求的逻辑。此结论是静态接线事实，具体请求内容仍需运行观察。
不能说所有任务的事实覆盖必为 0：题面、项目元数据或前序输出也可能出现有关内容。

现有 `tests/test_runner_dlp.py:8` 只断言 final_dlp_scan 被调用及输入包含 Repository Evidence；
`tests/test_cli.py:68` 检查十件 artifact 与三类 trace。均未证明摘录实际进入最终消息。
因此需增加只观察、不改变消息的边界；不得为获得漂亮 baseline 顺手修接线。

## 4. 运行与评分观察面

- Legacy 返回值 0/2/3/4 见 `runner.py:60`、`:208`、`:270`、`:273`；4 可对应 completed
  且 degraded/requires_review，不能一律当“未执行”。失败路径可能只有 run-*-error.json。
- `runner.py:404` 的 run_id 仅由 repo 路径和 requirement 派生；同 case 重跑必须另记 attempt_id
  与独立输出目录，不能用稳定 run_id 去重掉真实尝试。
- `src/specflow/artifacts/store.py:41` 保存 sources、analysis、generation、review、工具与 trace，
  没有保存实际 LLMRequest.messages。sources.json 是 Collector 观察面。
- `evaluation/validators.py:13` 声明 Legacy 十件文件；`:35` validate_artifacts 同时检查结构、
  lineage、trace、工具、来源、敏感模式。这是混合 findings，不能全部重命名为 task_success。
- `benchmark.py:164` 的七件/六 Schema profile 对 Legacy 不适用；旧 profile 保留原名/原始 finding。
- task_success/citation_support/fact mapping 的统一自动 scorer 仍 unknown。按冻结合同准备逐项
  证据与人工复核，不造关键词代理分数；safe_abstention 的终态 mapping 不足时保持 unknown。
- `workers/analyze.py:281`、generate.py:341、review.py:419 的 trace 是每 worker 的最终响应摘要，
  失败时可回退 0，不能证明所有重试的 usage。`benchmark.py:219` 又仅聚合 passed。
  不完整成本只保留已证实的小计；full_total=unknown，comparison_status=not_comparable。

## 5. 公平性与运行身份缺口

- `runner.py:64` 的 effective_model 来自参数；但实际 HTTP payload 使用
  `src/specflow/llm/providers/openai_compatible.py:97` 的 config.model。
  运行时必须记录非敏感配置模型并核对参数/请求/响应身份，不能只信 manifest。
- `runner.py:101` 的 max_selected_files 是 min(max_files, policy 限额)，max_tool_calls=20；
  `runner.py:134` 使用 per-agent token policy，fallback 在 `:144` 固定 max_retries=1。
  仅比较两个 policy JSON 相同不足以证明有效限额相同，Day 11 必须复核实际接线。
- `policy/models.py:100` 默认 max_llm_calls=10；Legacy 与 Multi-Agent 不同拓扑的调用量差异
  是实验因子派生，不在 Day 10 为方便运行调高限制。
- 本窗口 Provider/model/live 配置与新基线输出均未确认，状态 unknown/not_run；不读取凭证内容。

## 6. 处置与恢复

最小适配提案：[T-075](../../tasks/T-075-dataset-v1-legacy-dev-adapter.md)。
本次范围 M/R1，只读一条 Dataset→产品→观测→报告链；若实现 T-075，接口/跨文件变更按 L2 处理。
扩读 Worker/ContextBuilder/Provider 是为闭合最终消息与真实模型身份，未开展全仓库审计。
不启动整体 Ownership Gate，不借 Day 10 修产品 Context 接线或完整 usage ledger。

下一步：学习者 Review 第一轮适配/原样基线边界；明确批准后冻结 T-075，才可实施。
