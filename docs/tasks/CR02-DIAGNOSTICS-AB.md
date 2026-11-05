# CR02 A+B：离线归档诊断

2026-11-05 用户已确认本任务及下列修订验收。基线
`99a8baa0c2de38751a6ccce48d8b97e85ad1ec90`，唯一 checkout 为
`C:/Users/50469/specflow-h04-f03-20261023`。B1/B2 等已有工作区改动保留。

## 授权与交付

只新增本实施单、`scripts/contract_review/diagnose_review.py`、
`tests/contract_review/test_diagnose_review.py` 和 `docs/reports/CR02-DIAGNOSTICS-AB.md`，
执行必要离线验证。不提交、不推送、不读取凭据或 Holdout、不恢复 F01 oracle 复核，
不调用真实模型。C/D、在线查询、采集器和运行时修改不在本任务内。

## 入口和证据契约

- `--evidence` 显式输入 F01 事件数组或 B2 事件字典归档，最多 16 MiB。
- 用 `--report-revision-id` 选历史报告，或 `--review-id --job-id` 选失败任务。
  仅在归档完整、唯一失败任务可证实时省略 job。不得把当前状态套到旧报告。
- 可另带 `--trial-ledger`（最多 8 MiB）。F01 按同试次唯一完整 JSON 匹配，
  核对 reservation 摘要和对应 transport-entered；重复候选或覆盖不足为无法判断。
- B2 adapter 实收没有 call ID。可带 `--b2-export-source`，显式提供已审阅的
  B2 导出测试源码快照。本版只识别摘要
  `73e33e182ad304c77dd8a3ea35eff3949798d5fe85c7d9336e71aea4765f286d` 对应的
  Store rowid / adapter 顺序契约。调用方负责选择与归档对应的导出来源；摘要识别
  证明所用代码契约，不是归档来源的数字签名。来源未知时不使用顺序配对。
  全归档先核对数量、call ID 和 review/input/job，再筛选主体。
- `--compare-review-id --compare-job-id` 显式选择同一归档内 H03 的 A1；主体选 B。
  沿保存的 resolution 和原报告追溯 A0，不以输出猜测认定泄漏。
- 归档内路径仅作说明，不跟随读取文件。复用 strict_json、canonical、digest 和 B1
  identifier。严格 JSON、身份、来源摘要与正文检查各自保留结果。
- `--output` 必须为新目录。先完成同源 JSON/Markdown，再发布目录。
  退出 0 表示产物生成成功，2 表示参数/选择/归属错误，3 表示解析或 I/O 错误。
  业务失败或证据不足仍可正常生成诊断。

## 输出与判断

JSON 记录 subject、source_coverage、timeline、context_checks、business_acceptance、
evaluations、gaps、findings。默认输出身份、状态、字段位置和指纹，不复制正文。
引用采用来源文件、记录身份与 JSON pointer/JSONL 行号。工具与模型投影分开。
宿主等待、物理收尾/用量、业务采用分轴；同一调用的早期 UNKNOWN 与晚到并存。

请求相等、必需内容完整、指定答案隔离分别判断。证据使用 PRESENT、MISSING、
NOT_CAPTURED、NOT_APPLICABLE、CONFLICTING；检查使用 PASS、FAIL、UNDETERMINED、
NOT_APPLICABLE。已有确定 FAIL 不因缺证被覆盖。原采集状态原样保留，派生完整性
单列。review 序号跨 job 跳号本身不判缺证。

完整性期望来自完整冻结输入，不能由实际投影反推。父分析和固定复核检查采用记录、
项目规则、已采用权威片段、答案及候选引用。缺独立业务材料时全量完整性为
UNDETERMINED，列出已核对义务；有确定遗漏则为 FAIL。只有完整声明范围都满足时
才能 PASS。子任务未支持的义务明确列为缺口。预算错误没有阶段证据时不推断根因。

## 验收

| 编号 | 验证内容 |
| --- | --- |
| AC-01 | F01 trial02 无报告；45 事件、4 模型/2 工具、2 次拒绝；4 个唯一 transport 配对。宿主错误码与原提案重建的外部核验字段问题分开引用 |
| AC-02a | 三侧同步移除 rule_materials 通道，冻结期望不变；一致性 PASS、通道 FAIL，列明正文仍在 adoption_records |
| AC-02b | 三侧同步移除必需正文所有实际位置，相关摘要自洽、冻结期望不变；一致性 PASS、完整性 FAIL |
| AC-03 | 关联现有超预算用例验证调用前阻断；归档明确阶段与仅通用 BUDGET_EXHAUSTED 两种情形区别展示 |
| AC-06 | 在合法归属的 B 输入/请求注入指定 A resolution，隔离 FAIL；与错误事件归属的拒绝测试分开 |
| AC-07 | H03 guess_v1 正控制成立且 B 冻结输入与全部请求干净，指定答案隔离 PASS；受控输出评价独立，真实语义保留 NOT_RUN |
| AC-08 | 同 call ID 的早期 UNKNOWN、晚到收尾/已知用量、业务拒绝同时可见 |
| AC-09 | 子结果及父方拒绝同时可定位，不把返回当作采用 |
| AC-10 | 保留缓存历史与补采失败；删必要事件或截断配对样本导致缺证；正常跨 job 序号跳跃不误报；确定 FAIL 保留 |
| AC-11 | 报告与宿主状态可见，无独立语义评价维持 NOT_RUN |
| AC-13 | 错误 report/job、跨 review 事件引用拒绝；合法显式对照只输出摘要引用 |

另验：R04 新旧报告各自绑定历史 input/job；R05 业务 insufficient_evidence 与采集状态
独立；六个核心归档 14 份报告覆盖 62 模型和 34 工具调用；UNKNOWN 归档支持失败入口。
单独验证缺冻结输入、缺独立材料、未知导出顺序、歧义配对、坏 JSON、错摘要与输出失败。

## 验证方式

新增测试、相关 B1/B2/动态上下文/记忆/工作流/生命周期回归，然后全库 pytest、
Ruff 检查和格式检查。使用 `uv run --offline --no-sync`，测试继承现有真实 HTTP
阻断，并移除子进程中的 Provider/服务环境变量。历史归档只读复验，不重跑试验。
具体命令、产物、失败及修复、结果写入完成报告。
