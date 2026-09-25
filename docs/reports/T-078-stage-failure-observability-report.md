# T-078 完成报告 — Stage failure observability

- 日期：2026-09-25；状态：COMPLETE / 验证和独立审查通过 / 仅本地聚焦提交。
- 冻结规格：[T-078 v1](../tasks/T-078-stage-failure-observability.md)。
- 比较基线：`18690677f8c18a53a39a495eeaafa53c624ffb1a`。
- 分支：`codex/t078-stage-failure-observability`；保存项目的本地 checkout，无 worktree。
- 授权：用户阅读 P15-REPAIR-v1 后要求“新开一个窗口进行修复”；本任务成为唯一写入入口。
- learner diagnosis：PARTIAL；本报告和 AI 实现不计学习者掌握证据。

## 实现与边界

校验拒绝时创建不可变的 `_StageFailureAudit`，通过内部 ValueError 子类传到顶层；
只有可信 registry/scheduler 身份、stage、受控分类、来源及 scheduler 时间进入审计。
`manifest.error` 仍为 `MULTI_AGENT_RUN_FAILED`，新增 `failure_context`；
agent outputs 增加 `audit_only=true` 摘要；trace 增加同 run/coordinator 的 failed agent。
executor 分类仅来自允许表；身份不匹配优先记为本地校验失败。没有调用数、重试、Schema 放宽、
预算或 revision 改动。未验证正文/异常不打印、不落盘，usage/latency 未知时省略。

`_run_and_accumulate` 的校验 → append → prior_outputs.update 顺序不变；失败 stage 不进入
已接受集合。已有 Handoff failure_context、成功、零 Evidence 与政策失败保持原路径。
只持久化触发拒绝的一条记录，不能据此列出并行 stage 的全部失败。

产品文件只有 `src/specflow/runner_multi.py`；新增测试为
`tests/test_multi_agent_failure_observability.py`。原有测试未修改、删减或新增 skip/xfail。
不改 Provider/scheduler/Schema/Evaluator/Prompt/依赖，不读取正式 Holdout 内容或运行正式 Dev。

## 保护与可恢复工作集

本地证据根目录（不提交）：
`D:\Documents\ChatGPT\一个月冲刺\specflow-repair-backups\2026-09-25-160657-T078`。
其中 `inventory.json`、`tracked.diff`、`files/` 保存启动材料；447 文件、1880456 字节，
4 个指定学习文档/raw JSON 样本逐字节比对一致。原件没有移动或覆盖。
只复制明确 Day10/Day11 attempts 路径，不扫描配置、凭证或 Holdout。

验证包装 `validate.py` 与 `*-isolation.json` 在同目录。包装先真正删除全部
`SPECFLOW_LLM_*` 再导入项目，拦截真实同步/异步 HTTPTransport 并在 pytest 结束检查计数。
MockTransport 正常使用；实际启动 Python 子进程确认无 Provider 键，测试中的子进程再清理环境。
允许 Git、Python 标准库 Windows 版本查询的精确命令，以及经核对的唯一临时 Mock worker。
worker 仅允许 `specflow.evaluation.dev_baseline --worker-input`，预先核对输入路径、repo/output
均在本次 basetemp 内且 `provider=mock / mode=legacy`，再通过 `child_guard.py` 启动相同入口；
子进程导入产品前断言环境无 Provider 键，拦截同步/异步 HTTPTransport，单独落计数报告，
父进程核对报告存在且计数为 0。它不是 OS 网络 sandbox，
`uv --offline` 也不是。没有读取、输出或发现真实凭证，没有修改用户持久环境。

## 验证执行记录

通用命令前缀：

```powershell
uv run --offline --no-sync python -X utf8 '<本地证据根>/validate.py' <运行标签> <pytest 参数>
```

每次指定新 `--basetemp`，此前失败/成功 Artifact 均保留。相关回归参数为 `-v` 加
`tests/test_cli_multi_agent.py tests/test_agent_adapter.py tests/test_scheduler.py
tests/test_execution_policy.py tests/test_runs.py tests/test_fallback.py tests/test_cli.py`；
修后还包含新测试文件。

| 标签 | 命令/场景 | 实际结果 | HTTP 尝试 |
| --- | --- | --- | --- |
| baseline | 修前相关回归，初始包装 | exit=2，收集被包装拦截，非产品失败 | 0 |
| baseline-fixed | 修正包装后，产品仍未修改 | exit=0；120 passed、1 skipped、1 warning | 0 |
| red | 新增测试，产品未修改 | exit=1；18 failed、2 passed，缺 failure_context | 0 |
| green | 初次补丁后 focused | exit=1；19 passed、1 failed，新测试对旧 Mock shape 假设有误 | 0 |
| green-fixed | 更正该新测试并补本地 Schema 日志脱敏断言 | exit=0；20 passed | 0 |
| related | 新测试 + 7 个相关回归文件 | exit=0；140 passed、1 skipped、1 warning | 0 |
| full | 首次全量 `-v` | exit=1；831 passed、1 failed、3 skipped、3 warnings，Mock 子进程被包装拦截 | 0 |
| child-fixed | 更正包装后重跑确切失败用例 | exit=0；1 passed；1 个合成 Mock worker | 父/子均 0 |
| full-fixed | 包装修正后必要全量 `-v` | exit=0；832 passed、3 skipped、3 warnings，55.50s | 父/子均 0 |

过程裁决（不隐藏失败）：

1. 初始子进程 allowlist 只许 Git，SQLAlchemy 导入触发 Python `platform.machine()` 的 Windows
   `ver` 查询，被隔离包装阻断。只允许标准库精确的 `ver` / `command /c ver` / `cmd /c ver`，
   所有子进程仍显式删除 Provider 键。未改产品或旧测试。若该判断错误，包装会额外允许本地版本查询；
   不允许任意 shell 命令或 Provider 子进程。
2. 新 Stage1 测试曾断言已接受 Mock envelope 有 `success=true`。历史
   `RepositoryAnalystAgent.execute` 实际省略 success，gate 使用默认 true；已改为检查原 shape、
   schema_validated 和确定性 summary。产品不为新测试伪造字段。若该判断错误，可能漏掉显式 success
   字段改变；既有真实 adapter 测试与成功路径回归另外覆盖该合同。
3. 首次全量的唯一失败为
   `tests/test_dev_baseline.py::test_child_receives_no_annotations_and_records_actual_messages`。
   它通过产品 `launch_worker` 间接启动 Python（只扫测试文件的 subprocess 文本未覆盖这个调用链），
   被初始包装阻断，未执行该子进程。确认临时输入 Mock 边界后，增加上述确切入口的子进程哨兵。
   单用例通过后才重复必要全量；未更改/跳过原测试。若判断错误，可能放行错误的子进程，因此包装
   同时验证路径在新 basetemp、provider/mode、无凭证环境和父/子 HTTP 计数，不泛化允许 Python。

静态检查：`uv run --offline --no-sync ruff check .` exit=0；
`uv run --offline --no-sync ruff format --check .` exit=0（217 files）；
`git diff --check` exit=0。修前与 related 的 skip 为既有 Windows symlink 权限限制，
warning 为既有 Starlette TestClient/httpx 弃用提示；未增加 skip/xfail。
全量另外两个 warning 为既有 `TestStrategyAgent` / `TestStrategyOutput` 类因构造器不作为测试收集；
三个 skip 分别位于 test_repository_tools、test_runs、test_scanner，均为 Windows symlink 权限。
full-fixed 隔离记录：246 个子进程已清理环境，1 个临时合成 Mock worker，父 HTTP=0、子 HTTP=0。
初始完整运行因包装阻断未通过，不能冒充全绿；full-fixed 才是最终全量证据。

## AC 与审查记录

| AC | 本次对应证据 |
| --- | --- |
| AC-01/09 | `test_required_failure_artifacts_agree_without_running_specialists`：RED→GREEN，对外三个 Artifact、父子关联、完整性、调用计数 |
| AC-02 | `test_real_adapter_failure_classification_survives_stage_gate`：JSON/Schema 两例，真实 adapter + FakeLLM，调用一次 |
| AC-03 | `test_local_validation_overrides_untrusted_identity_and_status`：Schema/非对象/两种伪造身份，本地来源且敏感日志无泄漏 |
| AC-04 | `test_later_rejected_stage_preserves_only_previously_accepted_outputs`：Stage0 保留、stage=1、三个 specialist 只见旧输入、Synthesis/Review=0 |
| AC-05 | 五种缺失/畸形分类和三种合法分类测试；100000 字符正文、合成 secret/path；摘要 <512 字符、整组 <12000 字节 |
| AC-06/07 | 既有成功输出/handoff/metrics、零 Evidence、Handoff integrity、budget、revision 测试包含于 related，全部通过 |
| AC-08 | write/size 两例，无虚假完整标记，写盘异常不覆盖原分类 |
| AC-09 补充 | `test_rejected_stage_does_not_mutate_accepted_state` 保证 prior/accepted 不变；缺 timing 用 null，未知 Token/latency 省略 |
| AC-10 | 每次 isolation JSON 的真实 HTTP 尝试=0、导入前无 Provider 键、实际子进程继承检查及子进程环境清理 |

2026-09-25 独立只读审查 `review_t078` 已完成：没有 Critical / Important / Minor finding，
结论通过；核查了身份、分类、脱敏、接受集合隔离、并行单项边界、缺失计量、Handoff/成功/预算/
revision 与 Run API/评估消费者兼容。审查者未运行测试，运行证据由本任务负责。

审查中考虑但本批不裁决的行为，执行者逐项裁决为保留既有合同：

- scheduler 返回前异常/超时/预算的 agent 级审计仍 unknown；扩修会越过冻结范围。
  代价是这些路径仍没有新增 agent 级记录。
- 既有成功 Mock 省略 success，旧 accepted trace 可能标 failed，且旧 span 使用零 usage 默认；
  都是未修改行为，当前补丁只禁止新失败 span 伪造计量。代价是旧成功 trace 的诊断限制保留。
- Evaluator 仍要求完整成功 Artifact 集合，不利用新 failure_context 细分；本批禁止修改评分合同。
  代价是自动评分不会因本修复变细，也不声称分数提高。
- 历史 Provider 根因、正式 Dev/Holdout 表现和 learner ownership 无新证据；保持 unknown/PARTIAL。
  代价是这些问题仍需独立授权和本人证据，不自动关闭整个 RQ2-01。

没有 deferred minor 或待修审查问题。未按“顺手改善”修改旧成功 trace、预算或 Evaluator。

## 实际 Artifact 前后对照

两个运行均使用新临时合成仓库、相同触发，不覆盖原 F15-01。路径位于上述本地证据根：

- 修前：`red-artifacts/test_required_failure_artifact0/artifacts/run-multi-b4279db7cb2d/`。
- 修后：`green-fixed-artifacts/test_required_failure_artifact0/artifacts/run-multi-3deafe8570db/`。
- 结构化摘录：`artifact-comparison.json`；原 Artifact 保留，可核对各自完整性文件。

| 对外观察 | 修前实际 | 修后实际 |
| --- | --- | --- |
| exit / workflow_state | 3 / failed | 3 / failed |
| specialists / stages_completed | 0 / 0 | 0 / 0 |
| manifest.error | MULTI_AGENT_RUN_FAILED | MULTI_AGENT_RUN_FAILED |
| failure_context | 字段缺失 | stage_result_validation、可信 Analyst、stage "0"、SCHEMA_VALIDATION_FAILED、executor_reported |
| agent-outputs | `{}` | `stage-0/repository-analyst-agent-v1` 下固定审计摘要 |
| traces | 只有 run/coordinator | 新增一条相连的 failed Analyst span、stage 0、分类/来源、scheduler 时间 |
| usage / latency | 没有 agent 观察 | 新失败 span 省略，保留 unknown，不写实际 Token=0 |
| 完整性 | `_COMPLETE` 和 hash 文件存在 | 同样存在且测试核对 SHA-256；写盘/超限反例没有完整标记 |

修后摘要（实际值）：

```json
{
  "agent_id": "repository-analyst-agent-v1",
  "role": "repository_analyst",
  "stage_index": 0,
  "success": false,
  "schema_validated": false,
  "degraded": true,
  "audit_only": true,
  "error_code": "SCHEMA_VALIDATION_FAILED",
  "classification_source": "executor_reported"
}
```

## 残余 unknown 与停止边界

此修复证明当前合成失败分类可以保存，不证明历史 Day11 16 例的 Provider/JSON/Schema 根因，
不恢复丢失的 usage，不改善或重评分 task_success。executor_reported 只表示 executor 的分类声明。
scheduler 直接抛错、超时、预算在结果返回前终止继续走旧路径；并行仅记录触发拒绝的一项。
写盘失败仍可能没有完整 Artifact，但不伪造成功。预算硬上限和同步线程停止能力不在本批改造。
Day14 报告 §4.1 保留，不因本批隔离通过而删除、改写或声称被豁免。

## 交付与回退

产品/测试、冻结规格、本报告共 4 文件构成唯一聚焦提交。Day15 CURRENT/execution card/learner review/
Retest Queue 仅同步实际状态并留在工作区，原历史改动、两份 Word、day-11.md、计划书、Day13/14
报告和原 raw attempts 均不混入提交。代码交付完成；learner diagnosis 仍 PARTIAL，本人关键 diff
解释和历史 S6–S7 根因仍待后续证据。没有自动启动下一批。

本报告首次引入提交就是修复提交，可确定性定位（避免在提交自身内容中写入循环依赖的 SHA）：

```powershell
git log -1 --diff-filter=A --format=%H -- docs/reports/T-078-stage-failure-observability-report.md
```

回退执行 `git revert <上面定位的提交>`，不覆盖原学习材料，不涉及数据库/索引迁移。
未提交场景先保存本批 diff，再仅逆向应用本批补丁；不执行 reset/clean/整仓恢复。
本次不推送、发布或创建 PR；现有备份与前后 Artifact 保留以供复查。

最终边界核验：启动备份中的 443 个原文件逐字节不变；另 4 个仅为已授权 Day15 状态同步，
learner 原始文本仍完整保留。80 个本地文档链接有效。暂存范围精确为上述 4 个本批文件，
`git diff --cached --check` 通过；其余历史/行政材料未暂存。证据：本地 `final-boundary.json`。
