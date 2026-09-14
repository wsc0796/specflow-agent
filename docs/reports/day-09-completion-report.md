# Day 9 完成报告

- 日期：2026-09-14。
- 唯一项目：`D:\Documents\ChatGPT\一个月冲刺\specflow-agent`。
- 源码与 Gold revision：`08e5a66f8ea8216433c72744adab92aa07d99c45`。
- AI 准备提交：`174ecfc`。
- Dataset/annotation version：`v1`；状态：`frozen_v1`。
- 冻结检查点 commit：`bf77d19455cb989984dc4f909e6e7ca4b4f91aaf`。

## 交付结果

- 冻结 30 个唯一 Repository Task：20 Dev + 10 `frozen_internal_holdout`。
- 类别分布为 Dev 5/5/4/3/3、Holdout 3/3/2/1/1，依次对应精确关键词、
  语义改写、多文件、无答案、安全/旧索引配额。
- 34 个不同事实级 Gold、65 处 revision/path/symbol/行号/原文定位通过检查。
- answerable Case 均有事实级 Gold；unanswerable 与 safety_reject 显式分开。
- isolation_group、Gold fact ID 和 Gold 来源文件均不跨 Dev/Holdout。
- 冻结 7 项核心 Evaluator 的 34 个 calibration Fixtures；每项具备 pass/fail/unknown，
  缺失敏感项另有 N/A。8 个现有核心 helper 调用匹配预期，其余保持 contract-only/not_run。
- Holdout manifest 固定 `used_for_tuning=false`、`execution_policy=run_once_after_freeze`、
  `independent_creator=false`、`independent_access_control=false`，执行数为 0。
- 教材合成数据、历史 12 条 portfolio benchmark、Behavior Suite 和正式 30 条任务保持分离。

## 学习者证据

- 正确解释 Recall、Precision、RR 和 RRF；完成一组 RRF 手算并说明融合不等于质量评价。
- 经纠正后区分文件命中、事实 Recall、Context Assembly、未命中与 unknown。
- Review D001、D006、D015、D018-D020 的排序、Context、answerability 与安全边界。
- Review Fact Recall、Citation Support、Token Completeness、Safe Abstention 的关键正反例和盲区。
- 最终正确判断 `contract_run_success=pass`、`task_success=fail`，区分结构合同与任务语义。
- 延续 Day 8 的 Holdout 有界决策：内部冻结、不用于调参、污染降级、替换产生新版本。

部分判断经历纠正，且 Dataset/Fixture 内容主要由 AI 编写，因此 Day 9 整体 ownership 为
`improving / partial`。不声称学习者独立标注 30 条数据、独立实现 scorer 或达到整体 C4 verified。

## 覆盖与已知缺口

- 四条安全配额实际均为安全边界：`safety_case_count=4/covered`。
- 旧索引为 `stale_index_case_count=0/not_covered`；固定源码 revision 没有索引运行时，
  stale-index runtime capability 为 N/A。这是评测覆盖缺口，不是当前产品 Bug。
- 新 Dataset 到旧 runner 的加载、Evaluator-only 字段投影与通用报告入口仍未实现；Day 10
  必须先完成最小适配和输入隔离，不能直接把旧 12 条 benchmark 当作本套 baseline。
- automatic fact scorer、semantic citation scorer、完整 Token ledger/scorer 和 task terminal
  profile mapping 保持 unknown/contract-only。
- `allowed_claim_after_execution` 当前尚未成立；只有 Day 21 实际一次运行后才可声明内部冻结验证。

## 验证

| 检查 | 结果 |
| --- | --- |
| `check_day09.py --include-holdout-authoring --execute-existing-core` | 30 Case、34 Gold、65 locator、34 Fixture、8 core execution 全部通过；正式 Case/Provider 调用均为 0 |
| 默认 `check_day09.py` | 只读取 20 Dev 与 manifest；Holdout 题面不读取 |
| `uv run --no-sync pytest -v --basetemp data/day09-final-pytest` | 777 passed、3 skipped、3 known warnings，30.78s |
| `uv run --no-sync ruff check .` | passed |
| `uv run --no-sync ruff format --check .` | 211 files already formatted |
| `git diff --check` | passed |

三个 skip 均为 Windows 符号链接权限相关；三个 warning 为既有收集/依赖提示。本次没有修改
产品源码、测试、Prompt、检索策略、阈值或依赖。全量回归中的历史 Mock 测试不作为新的
Legacy/Multi-Agent Dev baseline。

## 冻结纪律与下一步

Days 10-20 不使用 Holdout 内容或逐题结果调整 Prompt、策略、阈值或 Evaluator。Day 20
冻结运行配置，Day 21 只运行一次。若内容或结果用于开发，旧版本降级为
`contaminated_internal_check`；替换只能建立新 dataset version，不能恢复旧等级。

Day 9 在本报告和冻结检查点处结束。用户已要求新建独立 Day 10 窗口；它必须从冻结提交启动，
先验证 Dataset 加载、Evaluator-only 输入隔离和评分观察面，再决定是否运行 Legacy Dev baseline。
