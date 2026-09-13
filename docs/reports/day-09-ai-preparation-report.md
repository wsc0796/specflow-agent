# Day 9 AI 准备完成报告

- 日期：2026-09-13；任务：先完成可由 AI 独立完成的数据、Fixture、格式与机械核验。
- 唯一项目：`D:\Documents\ChatGPT\一个月冲刺\specflow-agent`。
- 源码基线：`08e5a66f8ea8216433c72744adab92aa07d99c45`。
- 本轮状态：`AI_PREPARATION_COMPLETE`；Day 9 状态：`LEARNER_REVIEW_PENDING`。
- Dataset/annotation version：`v1-draft.1`；frozen=false，不作最终冻结或语义评测成功声明。

## 已交付

| 交付 | 证据 |
| --- | --- |
| 30 个唯一正式 ID 对应的题面、Gold、属性、answerability、版本与组 | `docs/study/datasets/v1/dev.json` / `holdout.json` |
| 三锚点及 20 Dev 源码审查材料 | `docs/study/datasets/v1/anchors.json` / `dev-review.md` |
| 7 项 Evaluator 的 34 个 Fixtures 与完整预期 | `docs/study/calibration/v1/fixtures.json` |
| 不展示答案的 Fixture 输入视图 | `docs/study/calibration/v1/fixture-review.md` |
| 版本、输入隔离、等级与访问用途 | `docs/study/datasets/v1/manifest.json` / `holdout-manifest.json` / `access-log.jsonl` |
| 数据核验与仅调用现有核心的校准入口 | `docs/study/check_day09.py` |
| 最小恢复与教学审查导航 | `docs/study/CURRENT.md` / `day-09-execution-card.md` / `day-09-review-pack.md` |

20 Dev 配额为 5/5/4/3/3，10 Holdout 为 3/3/2/1/1，顺序为精确关键词、语义改写、
多文件、无答案、安全/旧索引。安全场景来自现有边界；没有把未实现的旧索引拒绝当事实。
三锚点引用既有 Dev ID，不额外增加 Case。教材与 Behavior/历史 portfolio/calibration 均独立。

## 验证证据

| 命令/检查 | 实际结果 |
| --- | --- |
| `.venv/Scripts/python.exe -B docs/study/check_day09.py --include-holdout-authoring --execute-existing-core --output-dir docs/study/evidence` | 30 条、配额、34 个不同 Gold 事实、65 处 revision/symbol/行号/原文匹配；跨 split 组/事实 ID/Gold 来源文件均无重叠 |
| 默认 `check_day09.py` | 20 Dev 与元数据检查；不读取 Holdout 内容，不声称新一轮跨 split 检查 |
| 现有核心校准 | `_read_run` 4 次、`_validate_sources` 4 次，结果均匹配预期；其余 26 条 not_run |
| `uv run --no-sync pytest -v --basetemp data/day09-pytest` | 777 passed、3 skipped、3 warnings，13.94s |
| `uv run --no-sync ruff check .` | passed |
| `uv run --no-sync ruff format --check .` | 211 files already formatted |
| 文档与观察记录检查 | 10 个 Markdown、83 个本地链接、围栏与 34 个 Fixture observation ID 对齐通过 |
| `git diff --check` 与产品范围差异检查 | passed；src/tests/benchmarks/pyproject.toml/uv.lock 无修改 |

机器结果：[数据核验](../study/evidence/day-09-data-validation.json)、
[核心校准](../study/evidence/day-09-calibration-results.json)。完整回归日志在项目内
`data/day09-checks/pytest.txt`（忽略目录）。三项 skip 是 Windows 链接权限相关，三项 warning 为既有项。
现有回归测试会运行自身 mock fixtures；没有执行本次正式 30 条任务，未生成新的 Dev/Holdout baseline。

## 实现与证据边界

- 产品源码、测试、依赖、Prompt、检索策略、阈值与产品 Evaluator 实现均未改动。
  校验脚本只核验数据并调用两个现有只读 helper，没有新增语义 scorer 或 baseline runner。
- Fixture 内的预期裁决来自 AI，语义人工 Review 待完成。Fact Recall 正反例保存比例，
  不把 100% 覆盖擅自设成真实任务通过线。原始 helper finding/status 独立保留。
- 新数据到被测运行器的加载与字段投影没有实现；实际产品终态映射按未来 profile 记录为 unknown。
  后续被测源码应使用固定 revision，不能检索作者工作区中的 Gold/教学答案。
- 内部 Holdout 只在创建与作者机械核验时读取；不独立来源、不独立保管，执行数 0。
  manifest 尚未正式冻结，也尚不能声称完成一次性验证。污染后降级，替换不能恢复旧等级。
- 额外内容 digest 未生成；身份由版本、清单和 Git 检查点记录。
- Gold 来源职责分离降低了直接重叠，但不保证难度一致或语义完全独立；保留在关键 Review 中。

## 学习者与下一步

本轮 AI 工作完成不提升 learner ownership。前一次已公布结果的概念实验只算演示；学习者仍需
提交未公布题目的手算/预测，Review Dev 关键 Gold、Fixture 预期、manifest，并完成最终 Teach-back。
从 [精简审查包](../study/day-09-review-pack.md) 恢复，每轮一个主要判断，回答后给【正确答案】。
完成这些语义判断后再建立正式冻结版本；不因机械检查通过提前进入 Day 10。

本报告对应 AI 准备检查点，不是 Day 9 最终完成报告；冻结提交字段保持 null。
