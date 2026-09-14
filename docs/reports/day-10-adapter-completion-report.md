# Day 10 — T-075 适配完成报告

- 日期：2026-09-14；唯一项目：`D:\Documents\ChatGPT\一个月冲刺\specflow-agent`。
- T-075：`IMPLEMENTED_AND_VERIFIED`；Day 10：`BLOCKED_LIVE_IDENTITY`。
- Dataset freeze：`bf77d19455cb989984dc4f909e6e7ca4b4f91aaf`。
- 被读源码/Gold revision：`08e5a66f8ea8216433c72744adab92aa07d99c45`。
- 启动 HEAD：`cb665b4357d5b39498c5ac4a2bdd05d86affceb5`。
- 本次代码与报告所在提交：`git log -1 --format=%H -- docs/reports/day-10-adapter-completion-report.md`。
- 规格：[T-075](../tasks/T-075-dataset-v1-legacy-dev-adapter.md)。

## 交付结果

1. 独立 Dataset v1 Dev loader，仅打开 manifest.json/dev.json，验证 20 个预注册 ID、split、
   类别配额、版本与 revision。prepare/execute 对照冻结 Git 内容，拒绝题面/Gold 改动；
   仅兼容 Git Windows checkout 的物理 CRLF/LF 转换，不改变 JSON 字符串中的转义换行。
2. 固定 revision 的 `authorized-source-v1` 快照：src、tests、README、pyproject、uv.lock。
   不包含作者 checkout 的题库、Gold、校准/教学答案或本次结果；准备后逐文件核对原 Git 内容。
3. 父进程保留 Case 标注，子执行输入只投影 requirement 加正常运行配置；子执行拒绝额外字段，
   不接收 Dataset 路径。Gold/answerability/properties 等仅在执行后写入 Evaluator 审阅材料。
4. Legacy 新增默认关闭的请求观察钩子：在预算检查后接收不可变消息副本，保持原 request、
   Provider 异常和重试语义。观察失败不会触发产品额外重试，缺请求文件不会伪装完整观察。
5. 按 attempt_id 独立目录保存运行前清单、返回/异常/中断、真实产品终态或 unknown、消息观察、
   原始结构 findings 与报告。成功、降级、失败不被过滤；中断后的未开始任务仍在计划中。
6. Day 11 plan-only 镜像配置共用 Case ID、输入投影、目标 revision 和报告协议；执行入口明确拒绝
   Multi-Agent。它是配置脚手架，不声称完成 Multi-Agent 请求观察或实际 A/B 验证。

旧 12 条 portfolio loader、旧 Evaluator、Legacy Worker Prompt、Evidence/Context 接线、预算与
检索参数均保留。没有引入依赖，Dataset/Fixture 冻结内容未修改，原有 Word 未暂存。

## 运行证据与关键发现

合成单行 marker 实验确认：同一段 `REPOSITORY_EXCERPT_MARKER` 已进入 sources.excerpts，
三个 Worker 的实际 LLMRequest.messages 中均没有它。观察开/关时三份结构化产品输出与
Collector 摘录一致；工具计时不要求相等。该实验复现了静态接线缺口，未修产品行为。

实际 Multi-Agent 的 `max_selected_files=min(10, policy...)`，Legacy 当前为 min(5, policy...)。
镜像协议将这项有效限额差异标为 not_comparable；公共配置字段一致不能证明实际限额一致。
来源为 `src/specflow/runner_multi.py` 的 EvidenceCollectionConfig 和 Legacy runner 的 evidence_config。
Day 10 不调整该限制，留待后续公平性判断。

旧七件/六 Schema profile 对 Legacy 明确 N/A。现有 Legacy validator 单列 raw findings；
它不替代 task_success。事实映射、引用语义、任务成功与拒答的默认状态保持 unknown，
等待按冻结合同校准/复核。Token 全体 attempted 保留，但末次 worker usage 无法证明完整成本，
因此 full_total/coverage=unknown、comparison_status=not_comparable；零尝试为 N/A。

## 验证

| 验证 | 实际结果 |
| --- | --- |
| 首轮 RED | 13 failed：独立 loader/harness 与观察参数尚不存在 |
| 适配及新增执行门的 focused checks | 24 passed；补充 CRLF/真实 Gold 改动回归 2 passed |
| `uv run --no-sync pytest -v --basetemp data/day10-full-pytest` | **802 passed、3 skipped、3 warnings**，40.11s；含本次 25 项新测试 |
| `uv run --no-sync ruff check .` | passed |
| `uv run --no-sync ruff format --check .` | passed，216 files already formatted |
| `git diff --check` | passed |
| `git diff --quiet bf77d19 -- docs/study/datasets/v1/dev.json docs/study/calibration/v1/fixtures.json` | exit 0，冻结内容未变 |
| `uv run --no-sync python scripts/run_dev_baseline.py` | exit 0，prepare-only；20 planned / 0 attempted / 20 not_started |

完整 pytest 输出：`data/day10/pytest-full.log`。三个 skip 是既有 Windows 符号链接权限限制；
三个 warning 是既有收集与依赖提示，无新增 skip/xfail 或忽略失败。所有新测试使用合成数据与
临时 Git 仓库；测试中的 Mock 执行不计正式 Dev。真实 Holdout 文件未读取、未执行。

## 已准备的本地材料

- `data/day10/target/`：固定 Git revision 的授权源码快照。
- `data/day10/legacy-dev/run-config.json`：Legacy 身份/Prompt/Policy/limits/Evaluator 字段与 20 ID。
- `data/day10/legacy-dev/day11-mirror-config.json`：同公共配置的 Day 11 plan-only 镜像。
- `data/day10/legacy-dev/prepared.json`：准备状态与零尝试计数。
- [适配验证摘要](../study/evidence/day-10-adapter-validation.json)：提交到仓库的精简证据。

上述运行材料在 gitignored data/ 下；用入口可重新生成。当前 config 为未冻结运行身份的准备稿，
其中 runtime 记录生成时的代码 revision/工作区状态；真正执行前须用已提交代码重新冻结身份。

## 真实运行身份 blocker

本进程检查只记录环境变量是否存在，结果如下；未读取 .env 或输出凭证内容。

| 必需配置 | 状态 |
| --- | --- |
| SPECFLOW_LLM_BASE_URL | 未设置 |
| SPECFLOW_LLM_API_KEY | 未设置 |
| SPECFLOW_LLM_MODEL | 未设置 |

所以尚未运行正式 Legacy 20 Dev，尚无 Legacy 语义质量分数；Day 10 整体不能宣告完成。
工具已就绪，后续需在同一运行环境中提供所选 Provider 身份。入口会核对指定 model 与实际
config.model 相同，拒绝脏代码身份、忽略模型参数、错误快照或冻结 Dev 被改动。

配置就绪后，在唯一项目目录使用：

```powershell
uv run --no-sync python scripts/run_dev_baseline.py --freeze-identity --provider openai-compatible --model '<实际配置的模型名>'
uv run --no-sync python scripts/run_dev_baseline.py --execute
```

执行命令读取已冻结配置，不接受临时模型覆盖，不自动顶层重跑。正式结果将写为
legacy-dev-report.json/.md、attempts.json 和执行后的 evaluator-review-inputs.json。
Day 11 的实际运行与接线必须在其任务中推进；Holdout 纪律保持原样。

## 学习记录

用户明确要求先完成 AI 可独立完成的工作，已据此停止逐轮提问。T-075 的代码、测试和报告均为
AI-authored，不计 learner ownership。本人运行前预测、关键 Diff Review、代表 Case 解释和
Teach-back 仍未完成，不因为测试通过而提前登记掌握。当前没有待重复确认的 PATCH 授权。
