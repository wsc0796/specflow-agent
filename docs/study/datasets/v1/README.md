# Dataset v1

- dataset/annotation version：`v1`。
- 仓库源码 revision：`08e5a66f8ea8216433c72744adab92aa07d99c45`。
- 状态：`frozen_v1`；于 2026-09-14 完成关键边界 Review 后冻结。
- 20 Dev + 10 frozen_internal_holdout；该等级描述目标纪律，目前没有执行结果。

## 使用入口

- [20 条 Dev 审查包](dev-review.md)：题面、事实级 Gold、必要条件、源码片段与禁止主张。
- [dev.json](dev.json)：正式 ID 对应的数据草案；三锚点 D001/D006/D015 只是引用，不增加数量。
- [manifest.json](manifest.json)：版本、输入隔离、分类配额与状态。
- [Holdout manifest](holdout-manifest.json)：只审元数据与证据等级，调参期间不读取题面文件。
- [access-log.jsonl](access-log.jsonl)：作者创建与机械核验用途；不声称独立访问控制。

## 数据与评分边界

1. 每条题面单独在 requirement；answerability、Gold、expected_properties、forbidden_claims
   和评测备注只属于 Evaluator。`model_input_keys=[requirement]` 是数据侧约定，新的运行投影尚未实现。
2. 评测对象必须是固定 revision 的授权源码。不能让被测检索器扫描包含本目录 Gold、
   教学答案或 calibration 资料的作者工作区。当前固定 revision 本身不包含这些新增资产。
3. 不放入 `benchmarks/cases/`。旧 benchmark 固定 12 条且无事实级 Gold 协议，新数据不能直接交给它。
4. fact_evidence_coverage 保存不同事实及必要条件；无答案/安全拒绝的 Recall 为 N/A。
   无答案题使用明确的缺失来源/运行状态不可得依据，不用空 Gold 猜标签。
5. legal_terminal_state 中 product_state_mapping 仍为 unknown：题目在要求源码解释或拒答，
   不是直接执行其中描述的故障。未来按实际 topology/profile 保存产品终态，不能把回答中的
   “某函数返回 failed”写成被测 Run 的实际 failed。
6. 安全/旧索引的 3+1 配额当前全部是 `scenario_type=safety_boundary`。manifest 明确记录
   `safety_case_count=4/safety_coverage=covered`、`stale_index_case_count=0/not_covered`；
   固定 revision 没有索引运行时，因此 stale-index runtime capability 为 `N/A`。
   未为了凑题实现索引，也不声称已经覆盖旧索引拒绝。
7. 同组重复事实保持一致并在同一 split；两个 split 的 Gold 来源文件也无重叠。
   这不证明语义问题完全独立，也不证明两个 split 难度相当；该取舍留给学习者审查。

## 核验

仅当前 Day 9 创建期可以显式读取 Holdout 作机械核验：

```powershell
& .\.venv\Scripts\python.exe -B docs/study/check_day09.py --include-holdout-authoring --execute-existing-core --output-dir docs/study/evidence
```

默认命令只读取 Dev 内容及 manifest，不读取 Holdout 题面，也不运行任何正式 Case：

```powershell
& .\.venv\Scripts\python.exe -B docs/study/check_day09.py
```

默认检查不能给出新一轮跨 split 比对结论，输出 `not_checked`；Day 9 全部机械检查记录见
[数据核验结果](../../evidence/day-09-data-validation.json)。精确原文/字段检查不替代语义 Gold Review。

## 冻结与未决项

AI 已完成字段、源码映射、原文核验与组检查。学习者已 Review 关键 Gold/可回答性、
Fixture 边界、数据隔离与 manifest；未逐条人工审阅的 Case 保留 AI-authored provenance，
不冒充学习者独立标注。
来源、Gold 或期望属性变更要记录版本；Holdout 内容变化必须形成新 dataset version。
用于开发/调参后旧版降为 contaminated_internal_check，换题不能恢复旧证据等级。
不额外计算内容 digest；使用数据/标注版本、文件清单与 Git 冻结检查点记录身份。
