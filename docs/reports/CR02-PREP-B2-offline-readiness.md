# CR02 PREP-B2 离线验证报告

日期：2026-11-05（Asia/Shanghai）。状态：**B2 三文件离线工程验证完成，11 项 AC 通过。**

唯一 checkout：`C:/Users/50469/specflow-h04-f03-20261023`。
启动及收口核对 HEAD：`99a8baa0c2de38751a6ccce48d8b97e85ad1ec90`；
分支：`codex/h04-f03-offline-verification`。
B1/B2 准备资料为未提交工作树内容，不属于上述提交。

本轮只新增本报告、`scripts/contract_review/run_memory_case_prep.py` 和
`tests/contract_review/test_memory_case_prep.py`。未改 src、B1、候选材料和 oracle；
未创建 worktree、切换产品分支、提交或推送产品仓库；隔离材料的 Git commit 仅为试验夹具。oracle 保持
`PENDING_INDEPENDENT_REVIEW / NOT_FROZEN`，真实语义为 `NOT_RUN`。

## 实现与验证结果

初次定向运行：新增模块 2 passed，1 warning，27.07s。
实际复现 B1 将工具 `request_projected` 的 tool/arguments 正文误判为
`REQUEST_BODY_MISSING`；新 B2 采集器通过原有 gap 钩子识别该类型并保留完整事件。
模型请求仍沿用 B1 messages 检查；其他缺证不豁免。
R03 已通过两个独立 review 采用同一正式决定、各自绑定 input 与 adoption 的工程检查。
上述为受控替身结果，不是模型语义正确性结果。

| 验证 | 实际结果 | 退出码 | 原始日志 |
| --- | --- | ---: | --- |
| 首次五例与 demo 组合 | 8 passed / 1 warning，82.45s | 0 | focused-01.log |
| B2/B1/正式记忆/检查点定向 | 177 passed / 1 warning，496.45s | 0 | focused-02.log |
| 最后三项定向检查 | 3 passed / 1 warning，77.97s | 0 | final-focused.log |
| 证据轴缺陷最小复现 | **1 failed** / 1 warning，1.86s | **1** | axis-repro-fail.log |
| 证据轴修正回归 | 2 passed / 1 warning，18.63s | 0 | axis-fixed.log |
| 修正前全库，保留历史 | 1743 passed / 3 skipped / 3 warnings，3042.94s | 0 | full-suite-01.log |
| **修正后最终候选全库** | **1743 passed / 3 skipped / 3 warnings，788.16s** | **0** | **full-suite-02.log** |
| 最终全库 Ruff check | All checks passed | 0 | ruff-check-02.log |
| 最终全库 Ruff format --check | 305 files already formatted | 0 | ruff-format-02.log |

补采反例实际表现为 `collection_complete=false` 但缓存的 `evidence_status=COMPLETE`。
已在新采集器 gap 钩子同步设置 `INCOMPLETE`，并在真实历史补采和非法正文测试中加入断言。
修正前源码与失败日志保留，第二轮全库在第一轮结束后顺序执行，未把子集相加声称全库通过。
3 个 skip 均为 Windows 符号链接权限；3 个 warning 为 Starlette TestClient 弃用提示及两个既有测试类收集提示。

## 已通过的定向工程检查

下表均已通过定向与最终全库工程检查。真实模型语义均为 `NOT_RUN`。

| 验收 | 实际行为与证据 |
| --- | --- |
| B2-AC-01 | CLI 只生成隔离 Git 材料；认证配置读取受阻断，无业务 HTTP；身份、请求、profile、source groups 或密封内容不匹配均在 API 写入前停止。 |
| B2-AC-02 | R02 同 input、规则集 2、同目标采用两条互斥原文；受控报告的 conflict 用法和 blocking rule_conflict 均引用本次真实 adoption。未自动回答。 |
| B2-AC-03 | R03 两个独立 review 复用同一正式决定、版本与原文，adoption 分别绑定自己的 input，只有一次正式发布，无重复批准。 |
| B2-AC-04 | R04 新 input 保留旧决定的创建效力，仅取消采用新决定；历史全文和规则集 1 可重读，新报告无当前规则冲突。 |
| B2-AC-05 | R05 创建仍有效；取消无有效 adoption 或其他取消规范。受控报告在取消目标保留 insufficient_evidence，采集证据自身完整。 |
| B2-AC-06 | H03 的 A 答案已持久保存并进入 A1 冻结输入和实际分析/复核请求；B 完整 Store 输入及所有实收请求无 A 答案与 resolution ID。 |
| B2-AC-07 | 独立 demo 的 A0/A1/B 采用 2，C 采用 3；本次答案与后续 withdraw 为独立操作；C 保留历史 deny 原文但不作当前支持/冲突。 |
| B2-AC-08 | 发布同键同载荷返回原响应；改载荷、旧 CAS、外来决定引用被拒绝，随后合法发布仍成功，未污染规则版本。 |
| B2-AC-09 | 正式 report/input/question/target 引用来自实际响应；非唯一或不允许的题目停止答题。部分 200 不派生，最后 202 只生成一个后继；重放不再入队。 |
| B2-AC-10 | 核心五例与 demo 共 62 次模型调用，按物理 call ID 和顺序配对完整 payload；必需规则/目标正文另查完整性；本次合法答案与未触发/跨 review 答案另查来源。双方同时漏正文的反例被完整性断言拒绝。 |
| B2-AC-11 | 缺历史事件不能签证据完整；已知 FAIL 不被缺证改成待定。模拟远端 unknown 保留原状态、账本、阻塞与计划槽位，语义未运行。 |

测试节点在 `tests/contract_review/test_memory_case_prep.py` 中按执行单保留原 11 个名称；
另有 17 个边界/参数化节点，共新增 28 个测试节点。
跨项目正式决定的真实 ID 拒绝路径复用
`tests/contract_review/test_decision_scope.py::test_foreign_project_and_missing_decision_are_404`；
该旧节点已包含在本次 177 项定向回归中，新 B2 节点另查不存在的决定、CAS 与幂等重放。
H03 的故意错误猜测变体单独留证：B 工程输入干净，但受控替身仍输出 v1 归属；
该反例证明不能根据相似输出反推污染，不能计作真实模型语义通过或失败。

## 场景与统计边界

| 场景 | 阶段 | 受控模型调用 | 工程结果 | 真实语义 |
| --- | --- | ---: | --- | --- |
| CR02-R03 | A / B | 8 | PASS | NOT_RUN |
| CR02-R02 | A0 | 4 | PASS，等待合法裁决 | NOT_RUN |
| CR02-H03 | A0 / A1 / B | 18 | PASS，A1 已消费答案，B 重新澄清 | NOT_RUN |
| CR02-R04 | A_old / B_new | 8 | PASS，创建保留，取消报告受控偏离 | NOT_RUN |
| CR02-R05 | A_old / B_new | 8 | PASS，取消保留业务规则不足 | NOT_RUN |
| ABC-DEMO | A0 / A1 / B / C | 16 | PASS，独立工程门禁 | NOT_RUN |

仍为五个候选 case，demo 不加到语义分母；派生 input/job、负控制和重复测试均不增加样本。
上述数字仅统计六条核心编排，不代表整套 pytest 的替身调用总数。
未执行被查业务应用，所有 finding 的 `execution_verification` 保持 `NOT_RUN`。

## 运行与证据路径

所有仓库命令的 workdir 显式为本报告开头的唯一 checkout。
使用现有环境 `uv run --offline --no-sync`，没有安装依赖。
测试设置 `PYTHONDONTWRITEBYTECODE=1`、`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`，
按变量名移除 Provider/服务认证配置，注入假服务认证、进程内 TestClient 和 test adapter。
测试继承全库 HTTP 阻断，并在 B2 核心编排外增加传输层阻断与计数。

仓库外产物根：`D:/Downloads/agent学习/AI_HANDOFF/2026-11-05-B2-离线验证产物/`。

- `focused-01.log`：首次八项组合验证。
- `focused-02.log`：177 项相关模块回归。
- `final-focused.log`：证据轴修正前的三项复核，原记录保留。
- `axis-repro-fail.log` / `axis-fixed.log`：原失败与修正回归，不覆盖旧结论。
- `full-suite-01.log` / `full-suite-01/`：修正前的全库日志及原始产物。
- `full-suite-02.log` / `full-suite-02/`：最终候选全库日志及完整场景产物，包含 UNKNOWN 与缺历史事件负控制。
- `ruff-check-02.log` / `ruff-format-02.log`：最终静态/格式门禁；无后续代码修改。
- `evidence-index.json`：最终五例/demo/负控制、物理调用数量、原命令及多轴结果索引。
- `source-snapshot/`：本轮三个新增文件的最终副本与内容指纹；不是产品提交或人工冻结记录。
- `source-snapshot-before-axis-fix/`：首轮全库加载的两份源码快照。
- `command-results.jsonl`：两轮全库及最后三项复核的真实退出码。

最终复核命令：

```powershell
uv run --offline --no-sync pytest -q tests/contract_review/test_memory_case_prep.py::test_each_input_adoption_matches_actual_delivered_payload tests/contract_review/test_memory_case_prep.py::test_partial_answer_waits_and_last_answer_derives_only_one_job tests/contract_review/test_memory_case_prep.py::test_malformed_tool_and_model_bodies_are_not_exempted -p no:cacheprovider
uv run --offline --no-sync pytest -v -p no:cacheprovider
uv run --offline --no-sync ruff check .
uv run --offline --no-sync ruff format --check .
```

候选 oracle 未人工冻结不阻止本次替身工程检查；本报告不代签人工复核，也不授权真实模型试验。
真实入口、模型、试次和费用等条件仍由侧窗准入卡独立处理，本窗口未修改该卡。

## 收口状态

本轮 pytest 会话已全部结束，无待接管的 B2 测试。上下文实际占比不可读取，比例未知。
收口时 `git diff --name-only -- src` 为空，HEAD/产品分支未变；原有用户修改继续保留。
工作树另见 `docs/reports/CR02-observability-options-evidence-2026-11-05.md`，
不是本窗口创建的文件，未读取或修改，保留原状。

## 旧证据

B1 全库 1715 passed / 3 skipped / 3 warnings 为历史结果，未计作本轮 B2 结果。
原始产物：`D:/Downloads/agent学习/AI_HANDOFF/2026-11-04-B1-离线验证产物/`。
