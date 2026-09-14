# T-075 — Dataset v1 的 Legacy Dev 最小评测适配

- 日期：2026-09-14；version：`v1`；status：`IMPLEMENTED_AND_VERIFIED`。
- 本窗口实现授权：用户在看到 proposal-v1 后要求“现在先把AI可以解决的内容解决了，再给我谈后续的内容”。
  按该后续指令执行已展示的最小适配、测试和报告；不扩大到产品语义修复或静默 Live baseline。
  这是执行授权，不是 R1 学习判断；本人尚未作答，不据此提升 ownership。
- 后续同步的用户明确 PATCH 授权同时包括 Day 11 Multi-Agent 镜像脚手架与配置一致性测试；
  本 task 增加 plan-only 镜像输入/配置，执行分支明确拒绝 Multi-Agent，不运行其 baseline。
- 项目：`D:\Documents\ChatGPT\一个月冲刺\specflow-agent`；启动 HEAD：`cb665b4357d5b39498c5ac4a2bdd05d86affceb5`。
- 依据：[Gap Trace](../study/evidence/day-10-gap-trace.md)、[Eval v1](../study/eval-contract-v1.md)、
  [Evaluator v1](../study/evaluator-contract-v1.md)、[执行卡](../study/day-10-execution-card.md)。

## 1. 问题与唯一目标

新 Dataset 是带 cases 数组的 20 Dev envelope；旧 benchmark 是固定 12 条 Mock Multi-Agent，
旧 EvaluationCase 又需要另一套字段。现有结果没有最终消息观察与全 attempted 口径。
增加一个独立 Dev 入口，使原有 Legacy 产品在隔离输入、可复核观察面和诚实报告下运行。
禁止把旧套件改名、降低旧断言、修改产品 Prompt/检索/预算/拒答/Evaluator 语义来适应新题。

两种适配方案：推荐独立 loader + harness，保持旧入口与回归；不采用扩展旧 portfolio loader，
因为会耦合 12 条、类别、六 Schema、Mock Multi-Agent 与新合同。产品摘录接线修复另列后续问题。

## 2. 允许文件（批准后才写代码）

| 文件 | 责任 |
| --- | --- |
| `src/specflow/evaluation/dataset_v1.py`（新） | 显式 Dev 读取、数据身份检查、requirement 投影、固定目标快照准备 |
| `src/specflow/evaluation/dev_baseline.py`（新） | 父进程清单、无标注的 Legacy 子执行、输入观察、按 attempt 写报告、Day 11 plan-only 镜像 |
| `src/specflow/runner.py`（小改） | 可选只读请求观察钩子，默认关闭，保持产品请求与控制流 |
| `scripts/run_dev_baseline.py`（新） | 薄命令入口；仅 Legacy Dev，mock/live 显式区分 |
| `tests/test_dataset_v1.py`、`tests/test_dev_baseline.py`（新） | 合成数据/临时 Git fixture，隔离、观察、报告边界 |
| 本 task、Day 10 study/evidence、`docs/reports/day-10-*` | 规格、批准、验证与结果记录 |

不修改其他产品模块、旧 benchmark/evaluator、已有 30 条数据、calibration、依赖或 Word 文件。
若实现需扩文件或改变方案，先更新差异与理由，不用本表授权未来功能。

## 3. 输入与快照不变量

- AC1：只显式打开 `manifest.json` 与 `dev.json`；不 glob JSON、不装载整个目录，不提供 Holdout
  split/文件选项。验证 frozen_v1、suite/version/revision、精确 20 ID、唯一 ID、20 条 dev 与 5/5/4/3/3。
  路径清单/版本不符时在产品调用前拒绝，planned 保留，attempted=0；不从 Gold 筛选或跳过题目。
  prepare/execute 对显式 Dev 文件核对其冻结 Git 内容，防止只保留 frozen 标签却修改题面/标注。
- AC2：Case 标注仅父进程 Evaluator 保有；子执行只收到 requirement、target repo、output 与正常配置。
  case_id/attempt_id 只作 harness 关联，不进入模型任务正文。不得传完整 Case、answerability、Gold、
  expected_properties、forbidden_claims、legal_terminal_state、人工备注或分数。子执行分支不读 Dev。
- AC3：目标从本仓库固定 `08e5a66f8ea8216433c72744adab92aa07d99c45` 的 Git 对象导出，
  统一范围 `src/`、`tests/`、`pyproject.toml`、`uv.lock`、`README.md`，profile=`authorized-source-v1`。
  不按某 case 的 Gold 选文件；不包含 docs、evaluation、benchmarks、scripts、数据/答案材料、.git、
  本地未跟踪文件或本次输出。文件内容和相对路径保持 revision 原样；预检路径/link/导出清单。
  这是授权源码子集，不宣称扫描完整 checkout；Day 11 必须复用同一快照范围与内容。
  快照与结果位于本项目 `data/day10/` 下两个分离目录；产品工具 root 只绑定快照。
  本任务不创建第二实现仓库，不 checkout/reset 用户当前分支，不执行快照代码。
- 身份分别记录 Dataset freeze bf77d19、annotation v1、target revision 08e5a66、harness/product
  code revision 和 observer patch；冻结数据不被更新为运行结果，结果放独立文件。
- 隔离声明限于受测函数参数、子执行输入、受授权工具 root 与实际模型消息；不宣称操作系统级 sandbox。

## 4. 最小观察钩子与保持原样

- AC4：在 Legacy `_PolicyBoundLLMClient.complete` 成功预留调用预算之后、delegate.complete 之前，
  可选观察 worker 身份、该 worker 的调用序号、request.model、temperature/max_tokens/response_format，
  以及由 role/content 组成的不可变消息副本。不向 observer 暴露可变 messages 列表或真实 client。
- 原始 request 必须不变并只转发一次；不新增重试，不改变原异常、输出或终态。observer 失败只令
  observation incomplete，不能触发产品 fallback/retry；harness 无法完成记录时该次测量失效。
- 此接口默认关闭；Day 10 子执行显式启用，消息只写评测侧本地 observation 文件，与产品默认 artifact
  分开。仅使用上述源码快照与固定 Dev 文本，不读取/记录 API key、HTTP headers 或 .env。
  记录范围是 LLMClient 接收的消息，HTTP 发送是否成功单列，不把回调当 Provider 成功证据。
- 静态发现的 WorkerContext.project_context 未被三类 Worker 构建请求逻辑消费，保留原样。
  合成 marker 测试用于实证这个当前行为，不把“摘录必须进入模型”设为 T-075 通过条件。
  本适配不能修接线、补答案、改 Prompt 或为 baseline 调参；否则测量对象已改变。

## 5. 运行与评分口径

- AC5：冻结 20 条按 case_id 顺序各一次顶层执行；开始调用产品前写 attempt 记录，返回/异常后更新，
  不覆盖旧 attempt。planned/attempted/not_started 分开；0/2/3/4、异常、中断、失败、降级都保留。
  run_id 可以稳定复用，但 attempt_id 与输出目录必须独立；不自动顶层重跑。
- AC6：每 attempt 保存 exit code、产品 manifest.status 或 error 文件、artifact locator、观察完整性、
  实测 wall time 和终态来源。缺 manifest 的早退不伪造 completed/failed manifest；无法确定写 unknown。
  报告并列产品终态、Evaluator 状态/版本、verdict/value/finding/locator，不压成单个总分。
- Evidence 面分开：sources.selected_files/matched_files/excerpts 是 Collector 面；
  `receiver=analyze/generate/review` 的实际预算后 messages 是 Context 面。逐 receiver 保留；
  主报告明确 `generate` 为计划生成观察面，不能把三者无差别求并集或以文件数替代事实。
- task_success 依据冻结 expected_properties/forbidden_claims 审阅提交物：analysis/generation/review
  三份 JSON 与 technical-spec/test-plan 两份用户文档。每条属性给具体输出 locator；不事后挑最好的一份。
  AI 准备映射/候选评分及反例，学习者只审改变结论的分歧；AI-only 结论标来源，不写成 human-verified。
  没有已执行校准或足够复核证据时，该语义维度 unknown；不写自动关键词/相似度 scorer。
- 旧 `validate_artifacts` 可原样保留为 `legacy_artifact_validation` 及 raw findings；不是新通用
  contract_run_success scorer。七件/六 Schema portfolio profile 对 Legacy 为 N/A。
  新通用 structural profile 如无获批语义则 unknown，不能由 exit 0 推定 task pass。
- 路径 helper 仅在其 profile 适用时调用；来源不可读与不存在区分。合法空来源是否 N/A 按预声明
  profile 判断，不能靠删除现有 finding 调通过率。safe_abstention 的未知终态映射继续 unknown。
- 成本按全 attempted；现有 worker trace 是末次响应摘要，不能当完整请求 ledger。
  保留有依据的 observed subtotal 与来源；未能证明完整性则 full_total=unknown、
  coverage=unknown 或按已知缺失记录、comparison_status=not_comparable。零值必须有零调用证明。
  本 task 不补完整 Token scorer/ledger，不计算价格，也不把 Mock usage 当真实成本。
- unknown/N/A 均单列数量和理由；零尝试率为 N/A；条件均值必须标注 scored 覆盖，不能排除失败美化结果。

## 6. 运行前门禁与公平性

- AC7：先通过隔离/观察/报告测试，再冻结具体 run config；批准 PATCH 不等于提前运行 baseline。
  默认行为只准备输入/验证配置，必须显式执行选项才能启动正式 Dev。
- 真正语义 baseline 需要明确 live Provider/model；Mock 只用于合成测试/单列 contract smoke。
  当前真实运行配置为 unknown，禁止用环境恰好存在的凭证/默认模型静默启动。
  后续核对非敏感模型身份、实际 config.model 与参数一致性，保存可重放配置；不打印密钥。
- 固定当前 Legacy 默认 max_files=5、DEFAULT_POLICY、Worker 温度/Token 和固定 fallback 行为；
  不为凑通过率调参数。记录有效 max_files、字节/证据限制、调用与预算接线，不能只保存 policy 名称。
- Day 11 才执行 Multi-Agent，并复用 case、target、模型与测量协议；角色 Prompt/调用数的必然差异
  单列。模型/有效限额/评分观察面无法对齐时，对应维度 not_comparable，不在 Day 10 偷修。
- 镜像配置复用同一公共配置和投影函数；它不是已运行的 Multi-Agent adapter。
  已读到 Multi-Agent `max_selected_files=min(10, policy...)`，Legacy 为 min(5, policy...)。
  两者当前有效限额不同，必须显式记录为 not_comparable；不能用配置文件字段相同伪装公平性已验证。
- 没有运行配置、观察证据或 task 语义评分时，报告标缺口；不得宣告 Day 10 效果验证完成。

## 7. 测试边界与验证入口

本次 25 项新测试已纳入全量 802 passed；结果与范围见
[完成报告](../reports/day-10-adapter-completion-report.md)。以下为冻结验收矩阵；
实际断言以两份 test 文件为准，未以新 skip/xfail 隐藏失败。

| 验收 | 合成测试与反例 | 预期证据 |
| --- | --- | --- |
| AC1 | envelope/ID/数量/split/version/revision 正反例；访问拦截器遇 Holdout 文件打开即报错 | loader 只读显式 Dev；错误发生在产品调用前 |
| AC2–3 | 仅改 Gold/answerability/properties/备注为唯一 marker；requirement 和运行配置固定；污染 authoring docs；临时 Git 中植入非许可文件 | 子执行参数及所有实际 messages 无 marker；目标清单仅固定许可路径，输出不在目标中 |
| AC3 | 错 revision、目标为 authoring checkout、快照混入答案/链接/输出 | preflight 拒绝，不调用产品；不接触真实 Holdout |
| AC4 | 同一合成任务 observer 开/关；不同副本、observer 抛错、Provider 抛错与重试 | 转发请求/输出/调用数/终态一致；观察失败不能制造额外重试 |
| AC4 | 源码放唯一 Evidence marker，检查 sources 与各 Worker 最终请求 | 记录当前字段未消费行为；观察面不同不被包装成检索失败 |
| AC5 | 成功、降级、早退、异常、中断、未开始、重复稳定 run_id | 不漏 attempted，attempt_id 不覆盖；所有终态有记录/unknown 原因 |
| AC6 | 偏题但完整 artifacts、缺件、评测拷贝不可读、0/unknown usage、零尝试、已知缺失重试 usage | 结构/语义分离，保留 raw finding，成本不完整不比较 |
| AC7 | 默认 prepare、mock 明示、live 模型缺失/不一致、误传 Multi-Agent/Holdout | 不静默运行/降级/换 suite；本 task 不运行 Multi-Agent 正式 baseline |

新增测试只使用合成 fixture 和 tmp_path；正式 Dev 可做 loader 机械检查，不能在测试中循环跑 20 条。
现有 test_benchmark/test_evaluation/test_cli/test_runner_dlp 回归保持；旧 Multi-Agent Mock 测试如由
全量质量门调用，仍只是回归测试，不是 Day 11 baseline。不执行 calibration 新语义 scorer 冒充已实现。

批准后的验证顺序：focused tests → 相关现有测试 → `uv run pytest -v`、`uv run ruff check .`、
`uv run ruff format --check .`、`git diff --check`。无新依赖；已有环境下可加 --no-sync。
完整质量门和完成报告后才作聚焦提交；不得包含无关 Word 文件。

## 8. 当前决策门

用户已要求 AI 先完成可独立完成的工作；本 task 按已展示范围进入 PATCH。
教学判断延后，产品 Context 接线保持原样。正式 Live baseline 仍待有效运行配置与入口质量门。

T-075 实现与质量门现已完成；正式 Dev prepare-only 为 20/0/20。
本进程缺少全部三项 SpecFlow Provider 环境配置，Day 10 当前停在真实运行身份 blocker；
不再重复请求 PATCH 授权，也不将适配测试冒充正式 Dev 或 learner ownership。
