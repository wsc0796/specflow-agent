# Day 10 学习证据与恢复记录

- 日期：2026-09-14；启动 HEAD：`cb665b4`；唯一项目：`D:\Documents\ChatGPT\一个月冲刺\specflow-agent`。
- 当前模式：`REVIEW`；执行入口：[执行卡](../day-10-execution-card.md)。
- 用户已要求 AI 先完成 T-075 适配、测试、报告；后续同步明确 PATCH 和 Day 11 plan-only 镜像授权。
- Day 9 整体 ownership 保持 `improving / partial`；本日尚无学习者回答，不提前评级。

## 已完成与已读边界

已核对 cwd/Git 根、项目规则、路线、CURRENT、Day 9 完成报告、Eval/Evaluator v1 与 manifest。
已解析读取全部 Dev/calibration，完成现有评测入口、Legacy Worker、ContextBuilder、artifact、
Provider 模型身份与相关测试的静态追踪。源码/测试/依赖相对 08e5a66 无变化。
只读取 Holdout manifest 元数据，未读取 Holdout 内容，未执行任何正式 Case。
原有 Word 文件保持不动。AI 已准备 [Gap Trace](day-10-gap-trace.md) 与
[T-075 规格草案](../../tasks/T-075-dataset-v1-legacy-dev-adapter.md)，不计本人证据。

## 本人判断

R1 已准备，待本人回答：是否批准只增加评测适配/输入隔离/请求观察/报告，保留 Legacy
当前未消费 WorkerContext 摘录的行为，以形成原样基线；请说明先补接线会改变哪个比较前提。
不提前记录正确/通过/批准；收到回答后保存原文、【正确答案】、差异与边界。

## 当前停点与下一步

原 R1 提问延后；用户最新指令是先完成 AI 可独立工作。T-075 已冻结、实施并通过完整质量门。
已执行合成 fixture 与临时仓库测试；没有执行正式 Dev、Live Provider 或 Holdout。
初始三项 SpecFlow Provider 环境变量不存在。用户随后说明本机已有 DeepSeek 并要求 AI 自主定位；
已发现 DeepSeek Harness 和用户级凭证存在，OpenAI-compatible models API 返回
deepseek-flash/deepseek-v4-pro。凭证值未输出；选择 deepseek-flash 并冻结运行身份。

## T-075 实现与验证结果

- 新增独立 Dev loader、冻结源码快照、Legacy 子执行/记录/报告、Day 11 plan-only 镜像与 25 项测试。
- runner 唯一产品改动为默认关闭的只读请求观察；没有修改 Worker Prompt、摘录接线、策略或阈值。
- 全量：802 passed、3 skipped、3 known warnings，40.11s；Ruff lint/format 与 diff check 通过。
- 合成 marker 在 Collector excerpts 中存在、三个实际 Worker 请求中缺失；记录当前行为，不自动修复。
- Multi-Agent 当前选文件上限 10、Legacy 5，镜像公共配置一致不代表实际限额一致；已显式记 not_comparable。
- 真实 Dev 准备：20 planned、0 attempted、20 not_started。未读取真实 Holdout 内容，无正式 Multi-Agent 执行。
- [完成报告](../../reports/day-10-adapter-completion-report.md)与[机器摘要](day-10-adapter-validation.json)
  记录已验证范围、Provider blocker 和复现命令。无本人新回答，不提升 ownership。

## 正式 Legacy Dev 结果（AI 产物）

- 兼容性 smoke：configured/response model 均为 deepseek-flash；64/31 Token，1.811s。
- 正式运行：20 planned / 20 attempted / 0 not_started；20 returned、20 exit 4、20 completed/degraded。
- 60 个实际请求、0 Provider retry；Repository Evidence 进入请求 0，Evaluator-only/study 路径泄露 0。
- Collector 共 80 selected files、744 excerpts；因此最早错误观察面为 Context 接线，不能归为
  “DeepSeek 不会读代码”或“Collector 全部失败”。
- AI 对冻结属性复核：task_success 2 pass / 18 fail；D015/D016 pass。
- 14 个 answerable Case、23 个 Gold facts，最终请求事实覆盖 0/23。
- Token：56/60 调用有 usage，run completeness 16/20；已观测 subtotal 197779，full total unknown，
  comparison_status=not_comparable。
- Latency all attempted：mean 41.788s、p50 41.767s、p95 48.482s。
- D017 secret_detected 来自源码符号 `_bearer_token`，判 Evaluator false positive，没有凭证值。
- [正式报告](../../reports/day-10-legacy-dev-report.md)；
  [逐 Case AI Review](day-10-legacy-semantic-review.json)。这些均不提升 learner ownership。

Day 10 已收束。学习者尚未完成运行前预测、关键 Diff Review、代表 Case 解释或 Teach-back；
下一教学动作留到后续窗口，当前不要求用户补充模型信息。Day 11 需显式启动。

## 启动阶段行政核验

以下仅描述初始只读阶段；后续代码与测试结果以上节为准。

- 2026-09-14：五份 Day 10 相关文档的相对链接检查通过。
- `git diff --check` 通过；Git 提示 CURRENT 未来写回 CRLF，不影响本次检查。
- Git status 仅 CURRENT 修改、四份 Day 10 新文档及原有未跟踪 Word；源码/测试未变更。
- Word 文件仍存在，53205 bytes；没有读取正文、覆盖、删除或暂存。
- 没有运行 pytest/Ruff/产品/正式 Dev；本阶段证据是静态检索和文档检查，不是质量门完成。
