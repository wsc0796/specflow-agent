# CR02 A+B 离线归档诊断交付记录

日期：2026-11-05。状态：实现、针对性测试、归档复验及全库门禁完成（退出 0）。

授权为四个新增文件和必要离线验证；保留已有工作区改动，不提交、不推送、不恢复
F01 oracle 复核、不调用真实模型。基线为 `99a8baa0c2de38751a6ccce48d8b97e85ad1ec90`。

## 恢复入口

实施契约：`docs/tasks/CR02-DIAGNOSTICS-AB.md`。
唯一 checkout：`C:/Users/50469/specflow-h04-f03-20261023`。
历史 B2 索引：`D:/Downloads/agent学习/AI_HANDOFF/2026-11-05-B2-离线验证产物/evidence-index.json`。
历史 F01：`C:/Users/50469/AppData/Local/Temp/specflow-f01-deepseek-live-20261101-CNY2-trial02-001`。
上下文占用比例未知；按本文件和实施契约恢复，不把历史离线 PASS 解释为 live 授权。

## 实施与验证

新增四个文件：任务实施单、诊断脚本、诊断测试和本报告。没有改动运行时、采集器或
原始归档。入口从固定 report 或失败 review/job 选择历史对象，输出同源 JSON/Markdown。
正文留在输入归档，默认产物输出身份、状态、字段位置、摘要及原证据引用。

三个检查分别输出：请求在 adapter/transport 边界的一致性、冻结义务的正文完整性、
H03 指定 A resolution 到 B 的输入隔离。报告同时保留原评价、宿主状态历史、物理调用
收尾和业务采用。原归档 COMPLETE 与本次诊断材料不足可以并存，两个字段分别呈现。

### 验证记录

全部验证在上述 checkout 执行；测试子进程移除 `SPECFLOW_`、`OPENAI_`、`DEEPSEEK_`、
`ANTHROPIC_` 环境变量，设置 `PYTHONDONTWRITEBYTECODE=1`，不读取或打印它们的值。
使用现有 `tests/conftest.py` 的真实 HTTP transport 阻断。没有真实模型调用。

日志及诊断产物目录：
`C:/Users/50469/AppData/Local/Temp/specflow-ab-validation-20261105-rcjuq2h8`（定向、关联回归与归档复验）。
全库门禁复验目录：
`C:/Users/50469/AppData/Local/Temp/specflow-ab-validation-20261105-174914`
（`full-suite.log`、`full-exit.json`、`full-command.txt`、`parent-env-names.txt`、`head.txt`、`git-status.txt`）。

| 检查 | 实际结果 | 日志/产物 |
| --- | --- | --- |
| 首批诊断测试 | 43 passed | `focused-01.log` |
| UNKNOWN 等补充后的诊断测试 | 50 passed | `focused-02.log` |
| 最终诊断测试 | 55 passed，1 条既有依赖弃用告警 | `focused-final.log` |
| 关联回归 | 168 passed，1 failed；唯一失败为 Markdown 排序问题，已修复并由最终诊断测试和归档重渲染复验通过 | `related-01.log`、`related-command.json` |
| 历史归档复验 | 21 次导出通过；六个核心归档 14 份报告，按 job 去重 62 模型/34 工具 | `archive-final-summary.json` |
| 真实 B2 归档的受控副本 | AC-02a、AC-02b、AC-06 全部达到预期否证结果 | `controlled-archive-summary.json` |
| 全库 Ruff 检查 | 通过；既有 `tests/test_coordinator.py:113` 的 noqa 格式告警保留 | `ruff-check.log` |
| 全库 Ruff 格式检查 | 307 files already formatted | `ruff-format.log` |
| 全库 pytest（复验） | 1801 项收集；1798 passed / 3 skipped / 3 warnings；退出 0；653.99s | 新目录 `full-suite.log`、`full-exit.json`。旧目录的退出 1073807364（0x40010004，进程被外部终止）与 23% 截断日志保留为历史 |

测试命令：

```powershell
uv run --offline --no-sync pytest -v tests/contract_review/test_diagnose_review.py -p no:cacheprovider
uv run --offline --no-sync pytest -v tests/contract_review/test_diagnose_review.py tests/contract_review/test_review_evidence.py tests/contract_review/test_memory_case_prep.py tests/contract_review/test_dynamic_context.py tests/contract_review/test_project_memory.py tests/contract_review/test_dynamic_workflow.py tests/contract_review/test_lifecycle_and_queue.py -p no:cacheprovider
uv run --offline --no-sync pytest -v -p no:cacheprovider
uv run --offline --no-sync ruff check --no-cache .
uv run --offline --no-sync ruff format --check --no-cache .
```

### 验收对应

| 验收 | 证据与结果 |
| --- | --- |
| AC-01 | `archive-verified-f01`：无报告，failed/ACTION_PROTOCOL_ERROR，45 事件、4 模型/2 工具；4 个唯一传输配对、2 次原始拒绝、6 个重建字段问题。宿主错误码与重建归因分开 |
| AC-02a | `AC02a-diagnosis`：请求一致性 PASS，材料通道 FAIL，必需正文仍存在；对应参数化测试 `test_joint_omission_distinguishes_channel_from_body` |
| AC-02b | `AC02b-diagnosis`：三侧请求一致，冻结期望保留，正文从所有实际位置移除后完整性 FAIL |
| AC-03 | `test_budget_stage_requires_explicit_evidence` 两种阶段证据；关联 `test_mandatory_project_body_overflow_fails_without_truncation_or_call` 已通过 |
| AC-06 | `AC06-diagnosis`：正确归属的 B 请求收到 A 答案，隔离 FAIL；输出只给来源和字段位置 |
| AC-07 | `archive-verified-6-B`：guess_v1 的指定答案隔离 PASS，原受控 wrong_guess 评价保留，真实语义 NOT_RUN；normal H03 亦通过 |
| AC-08 | UNKNOWN 归档 `archive-verified-8-A` 保留未知远端结果和 null 用量；`test_actual_late_event_shape_keeps_early_unknown_snapshot` 保留早期 UNKNOWN 与后来已知用量，业务失败不变 |
| AC-09 | 诊断测试保留子结果及父方 rejected；关联动态工作流 adopted/partial/rejected 三种原测试已通过 |
| AC-10 | `archive-verified-7-A/B` 保留缓存事件、原 workflow FAIL 和补采缺口；诊断测试覆盖删详情、缺引用、截断配对、确定 FAIL 保留与合法序号跳跃 |
| AC-11 | 核心 14 份报告与宿主状态可读；全部真实语义仍为 NOT_RUN |
| AC-13 | 5 类归属拒绝、错误 report/job、显式双侧对照、摘要不带正文及不覆盖输出均通过 |

R04 的 `archive-verified-4-A_old` 和 `archive-verified-4-B_new` 分别绑定自己的 input/job、
规则集版本和冻结采用处置。R05 输出原报告的 `insufficient_evidence` 判断，不因采集
COMPLETE 而改写业务结论。目标级正式规则效力重算仍属于 C。

### 历史格式差异与修复

1. UNKNOWN 负控制只导出了 Store body，没有 call_id/job_id。首轮解析失败保存在
   `archive-initial-summary.json`。现在仅以已有唯一 projection 身份及完整对象匹配
   关联；无法唯一关联时保留 unbound 状态与缺口，不捏造调用身份。
2. Markdown 美化输出最初没有固定键序，JSON 回读重渲染比较失败。现在统一排序，
   55 项最终测试和 21 次历史归档的 JSON→Markdown 重渲染比较通过。
3. 关联回归日志含 Windows 本地编码的失败片段；收尾显示日志的包装命令发生
   UnicodeDecodeError。原 pytest 总结仍保存在原日志中：168 passed、1 failed。
   不把包装命令异常当作另一项产品测试失败。

## 使用示例与证据边界

F01 历史归档只读诊断示例，输出目录必须不存在：

```powershell
$abEvidence = 'C:/Users/50469/AppData/Local/Temp/specflow-f01-deepseek-live-20261101-CNY2-trial02-001'
$abOutput = Join-Path $env:TEMP ('specflow-ab-' + [guid]::NewGuid().ToString('N'))
uv run --offline --no-sync python scripts/contract_review/diagnose_review.py --evidence "$abEvidence/review-evidence.json" --trial-ledger "$abEvidence/trial-ledger.jsonl" --review-id cr_3c960583abde4aec97fa2d60f14bbc54 --job-id job_d998f4c572264378b8c4e6414320ddd9 --output $abOutput
```

B2 使用 `--report-revision-id`，并显式提供 `--b2-export-source` 指向已经核对的导出
源码快照。每次实际使用的完整 argv 已写入 `archive-final-summary.json`。H03 主体选 B，
另带 A1 的 `--compare-review-id` 与 `--compare-job-id`。不提供来源快照时，B2 请求
配对为 UNDETERMINED；不提供 H03 对照时，专项隔离检查为 UNDETERMINED。

普通归档没有全部案例材料的独立期望，因此全量正文完整性保留 UNDETERMINED；
已核对的冻结规则、答案和候选引用逐项展示，确定遗漏保持 FAIL。这是本次契约要求
的证据边界，不以已保存的原 B2 测试 PASS 替代本次检查。

F01 的 transport-entered 只证明通过本地传输守卫；不宣称供应商接收确认或模型内部
根因。受控归档修改是离线否证样本，不是新 trial。B2 通过不产生 live 资格。

全库门禁已于 2026-11-05 复验通过：退出 0，1798 passed / 3 skipped / 3 warnings。
下一步：按用户授权范围核对最终四文件差异；提交、推送等另行授权。
