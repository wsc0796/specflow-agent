# 并行修复契约协调与隔离集成报告

日期：2026-09-13。状态：**外部审查 R1 修复后本地验证通过，待重审候选**。

本轮未推送集成分支，未合并、关闭或 APPROVE 来源 PR，未改动远端 main。
没有开始 M9 T-071 或任何 M10 运行时实现。

## 目标、基线与输入

用户确认了“任务身份协调 → 隔离集成 → 运行契约适配 → 组合验证”的方案。
执行范围见 [集成任务契约](../tasks/INTEGRATION-runtime-repairs-2026-09-13.md)。

| 输入 | 固定提交 |
| --- | --- |
| main | 1b44127747a7f7b8bfd9118eb56006d867986b39 |
| PR #6：M9/M10 规范登记 | 02556b90aeec5fcc55dd7426bb3098dcf1e788f4 |
| PR #7：T-081 必需输出有效性 | 0ab5545c756ae68ef7f9cad88515d47915e0062c |
| PR #10：T-082 可信 prompt 打包 | 942f5d8a3e46ff0bced65931d0eb3bea5dd9fe4a |
| PR #8：T-070 single-flight / A01 | c54aaf703313764cf4ea1605eb883d8263ae9e52 |
| PR #9：无证据、handoff、学习文档 | c6c893c3a723a3f62c33265394ed1fcbf1c6029b |

- 分支：`integration/runtime-repairs-20260913`。
- 工作区：`C:/Users/50469/specflow-agent-integration-20260913`。
- 来源工作区和分支历史保留；PR #5 与独立 runtime-correctness 分支不在本轮范围。
- 本地装配保留来源提交祖先：规范分支快进；`77fcdec` 合入 T-081；`84be11e` 合入 T-082；`99e64db` 合入 T-070/A01 并适配离线 provider 夹具。最后的 PR #9 合并同时记录集成调整。
- 最终提交号在提交后的交付回复给出，报告不要求包含自身 SHA。

## 编号与文档协调

完整映射见 [任务身份映射](../tasks/TASK-IDENTITY-MAP-2026-09-13.md)。

| PR #9 原编号 | 集成编号 | 含义 |
| --- | --- | --- |
| T-070 | LEARN-001 | V5.1 学习环境 |
| T-071 | LEARN-002 | V5.3 学习环境迁移 |
| T-072 | T-083 | 无证据提前失败 |
| T-073 | T-084 | Handoff 完整性失败可观测性 |

8 份任务规范/完成报告全部保留，REQ/AC 编号及活动链接同步调整。
原分支名、日期、提交和独立验证计数继续作为历史证据；新增来源说明明确原路径和编号。

- M9/M10 的 T-070～T-080 语义和编号未修改；15 份冻结规范与报告与 `02556b9` 完全一致。
- M9 `docs/reports/T-070-completion-report.md` 与 PR #8 的 `c54aaf7` 完全一致。
- 没有在 M9 T-071/T-072/T-073 的完成报告路径放入学习或其他修复报告。
- CURRENT、day-01、day-06 只调整编号和路径，没有推进学习模式、进度或能力认证。
- LEARN-002 的 V5.3 规范注明是历史迁移，当前路线仍为 V5.3.2。
- T-084 原实现与后续 `2c6e0a9` 学习记录同步保持历史分界。
- CHANGELOG 保留 T-081 与 T-082 两项修复；AGENTS 保留修正后的 M6 历史声明和学习合同，独立分支旧测试计数未当作组合结果。

独立文档复查未发现编号、链接、历史事实或冻结边界遗漏。

## 运行契约适配

1. `_persist_failed_run` 同时保留 T-084 的安全 failure_context 和 T-070 的安全完成目录返回值。
2. 无证据与 HandoffIntegrityError 两个新增失败出口直接返回不可变 RunResult。EVIDENCE_NOT_FOUND、HANDOFF_INTEGRITY_FAILED 不再因裸整数与新接口不兼容而退化成 RUNNER_FAILED。
3. 前置失败产物完成原有写入、完整性文件和完成标志后才提供引用。诊断写入失败保留原始失败分类，日志不包含异常原文。
4. API 终态提交仍先于 follower 结果发布；真实运行线程退栈前不释放 ownership/permit。
5. 等价键版本明确标识组合后的最小内容 schema、打包 prompt loader、必需 evidence gate 和 handoff 分类。
6. D1 最小 schema、Agent mock 输出与 adapter 内容保持来源 `0ab5545` 一致；D2 prompt_assets、registry/security 保持来源 `942f5d8` 一致。
7. D1 离线 RecordingProvider 夹具增加明确的合成配置，以通过 T-070 的早期配置校验；真实 HTTP 阻断仍生效。
8. 10 个成功场景夹具补充真实匹配的 feature 源码；单字母 x 需求改为可搜索的 feature。没有放宽无证据条件、修改 selector 或削弱负向断言。DTO 身份测试进一步断言确实 completed。

本轮没有增加依赖、数据库列、Agent、重试层、缓存、分布式锁、调度系统或 prompt 内容。
保持原产物文件名、数据结构和哈希/完成校验；完整性失败的失信 payload 按原安全契约排除，详见下一节。

## 独立复核发现及修复

**INT-01：handoff 完整性失败时，原地篡改的 payload 仍可能被写入失败产物。**

- 首次状态：P2 / open；违反 REQ-084-4、AC-084-4。
- 定位：`src/specflow/runner_multi.py` 的 `_validate_stage_inputs` 与 `_persist_failed_run`。
- 原因：交给 validator 的对象与 stage outputs 共用引用；原测试只篡改 deepcopy 副本，因此未暴露真实对象被修改后再次序列化的问题。
- 独立复现：返回 3/failed_runtime/HANDOFF_INTEGRITY_FAILED，receiver 未执行，但有 `_COMPLETE` 的 agent-outputs.json 中出现篡改 sentinel。
- 修复：仅对 HANDOFF_INTEGRITY_FAILED 写空的 agent-outputs.json，保留安全 manifest/trace 标识及完成记录，不序列化该失信执行的 payload。其他失败仍保留既有阶段诊断输出。
- 新增原地篡改用例先红后绿，扫描全部失败产物确认不存在 sentinel。
- 独立复查确认原地篡改无泄漏；另外复验 CALL_BUDGET_EXCEEDED、MULTI_AGENT_RUN_FAILED 两类失败，分类与正常阶段诊断输出均保留，三条路径均正确清理。
- e19ec4f 当轮结论只验证了 summary 篡改分支。后续外部 R1 证明其他 envelope 变更会绕过专用分类；此前对完整缺陷族的关闭判断过宽，修复与复验见下一节。

独立复查产物：`C:/Users/50469/temp/integration-handoff-recheck-ze_jn708`。
这不等同于 GitHub 正式 APPROVE 或整个 M9/M10 已验收。

## 外部审查 R1 / P2 修复（2026-09-13）

修复起点：`e19ec4f4b10d4bdb0b29c931d5c676ed69c25aae`。用户提供的证据包
`specflow-review-e19ec4f-evidence.zip` 内 22 个文件校验和一致。本地 Windows /
Python 3.12 锁定环境只读复验为 4 failed、1 passed，与外部 Linux 补充测试发现一致；
随后用户明确授权修复。旧 bundle 和旧审查证据保持不变。

根因：hash 生成后修改 agent_id、role/output 类型时，envelope 检查先退出，实际
mismatch 未进入 HandoffIntegrityError；通用运行失败路径继续持久化含失信内容的
stage outputs。仅按错误字符串触发的旧隔离没有覆盖这些分支。

本轮生产修改限于 `handoff/validator.py`、`handoff/exceptions.py` 和 `runner_multi.py`：

1. 引用前缀与存在性检查后，先使用原 canonical_json_bytes 计算并比较当前 payload hash，
   再检查 envelope 语义。缺失引用保持普通校验错误；存在但为 null 的 payload 与缺失引用区分。
2. 真实 mismatch 仍抛 HandoffIntegrityError，并返回 HANDOFF_INTEGRITY_FAILED。
   hash 匹配但 envelope 原本非法时，仍抛普通 HandoffValidationError，不伪造完整性错误。
3. 新增窄 HandoffPayloadError 基类，沿用原有四个 audit_context 标识。不能规范化的集合、
   循环引用、混合键等以普通 MULTI_AGENT_RUN_FAILED 终止，但明确隔离失信 payload；
   不声称进行过成功 hash 比较，不保留原始异常链。
4. runner 对上述 payload-verification 家族显式传递 quarantine_payloads，失败 writer
   不序列化相应执行 payload。普通预算与运行错误不设置该标记，保留原阶段诊断。

未修改 canonical_json_bytes、RunResult/single-flight、数据库列、schema、prompt、
重试、调度、冻结规范或学习状态。新增异常没有增加一种对外 Run 状态或错误码。

| 最新验证 | 退出码 | 实际结果 |
| --- | --- | --- |
| 新单元测试红阶段 | 1 | 9 failed, 11 passed；覆盖 envelope 先检及无法规范化问题 |
| API 组合红阶段抽查 | 1 | agent_id、不可规范化、混合键三个场景失败 |
| 原外部审查完整探针 | 0 | 5 passed, 1 warning in 1.66s；四种 direct 篡改和 API 共享均正确隔离 |
| 当前 validator + 组合测试独立复核 | 0 | 35 passed, 1 warning in 3.59s；未发现本轮阻塞问题 |
| 本轮定向回归 | 0 | 197 passed, 1 skipped, 1 warning in 19.67s |
| `uv run pytest -v` | 0 | 920 passed, 3 skipped, 3 warnings in 24.60s |
| Ruff check / format | 0 / 0 | All checks passed；213 files already formatted |
| secrets / diff / cached 检查 | 0 | 通过；提交前对暂存内容再次检查 |
| 12-case benchmark / baseline 比对 | 0 / 0 | baseline 无变化 |
| 新 wheel 与独立 sdist 重建 smoke | 0 | 两轮各 10 项 PASS，非 editable 安装 |

本轮新增 23 个仓库场景：15 个 validator 场景与 8 个组合场景。覆盖真实 mismatch、
hash 匹配但 envelope 非法、缺失引用、正常输入不被修改、不可规范化，以及普通预算/
运行错误诊断保留。API 用例同时检查两个身份、一套工作、receiver 非执行、原 hash 和
sentinel 不进入失败产物、安全上下文、完成标记与 entry 清理。

本轮定向命令：

```text
uv run pytest tests/test_handoff_validator.py tests/test_runtime_repair_integration.py tests/test_run_single_flight.py tests/test_runs.py tests/test_api_security.py tests/test_cli_multi_agent.py tests/test_required_output_validity.py -v
uv run pytest <证据解压目录>/repros/test_review_contract.py -v -s --tb=short
uv run specflow benchmark --suite benchmarks/cases --repo benchmarks/fixtures/portfolio-python --output artifacts/envelope-fix-20260913 --baseline artifacts/envelope-fix-20260913/baseline.json
git diff --no-index --exit-code benchmarks/results/mock-baseline.json artifacts/envelope-fix-20260913/baseline.json
uv run python scripts/smoke_installed_wheel.py
```

本轮 wheel 与重建 wheel SHA-256 均为 `61662fb75aaf2c335411c9bf3527ba0020daaee2675b5d19a0d6d45e407034c3`；
sdist 为 `a0bacfe018d1d2bc7707f45a82745ecd5a7b6b9f0a2d6655e2bd01be6a77e886`。
它们是收尾文档更新前的最终运行时代码验证产物，不是发布版本。

R1 的上述已复现分支现有修复和独立复验证据；本候选仍待外部重审，不把测试覆盖外的
任意进程内对象修改或未授权攻击路径宣称为已证明安全。

## 组合行为覆盖

新增 `tests/test_runtime_repair_integration.py` 共 7 个场景：

- 无证据、无效必需输出、篡改副本、原地篡改，共 4 种失败的真实重叠 API 请求。
- 真实 DesignAgent worker 取消时，仍在运行的 peer 退出前保持 permit 与 ownership；退栈后正确取消并允许后续新 owner。
- API owner → direct follower、direct owner → API follower 两个方向。

测试通过 Event 明确保持 owner，确认 follower 在 owner 结束前加入；验证一套昂贵工作、两个持久化身份、正确错误分类、安全共享诊断引用、receiver 非执行与资源清理。无证据场景还验证零 provider 调用。

T-070 既有长 legacy manifest 回归、不可变结果、超时和取消回归继续通过。两个新增行为版本也进入等价键变化测试。原有全套测试未被跳过以获取绿灯。

## 实际验证记录

所有运行使用隔离工作区原锁定依赖，无 live provider 调用。

| 阶段/命令 | 退出码 | 实际结果 |
| --- | --- | --- |
| T-081 定向测试 | 0 | 38 passed, 1 warning in 8.86s |
| T-082 prompt/CLI 定向测试 | 0 | 35 passed in 1.56s |
| 初次 T-070 + D1 组合 | 1 | 33 failed, 77 passed；离线 fake 缺少早期配置 |
| 配置夹具适配后 | 0 | 110 passed, 1 warning in 7.61s |
| PR #9 新出口适配前 API 检查 | 1 | RUNNER_FAILED 与预期 EVIDENCE_NOT_FOUND 不符 |
| 出口适配后定向检查 | 0 | 3 passed, 38 deselected, 1 warning in 1.35s |
| 第一轮全量组合 | 1 | 13 failed, 875 passed, 3 skipped, 3 warnings in 19.87s |
| 成功夹具修正后相关检查 | 0 | 120 passed, 1 skipped, 1 warning in 9.78s |
| INT-01 原地篡改回归修复前 | 1 | sentinel 出现在 agent-outputs.json，1 failed |
| INT-01 修复后相关检查 | 0 | 23 passed, 1 warning in 3.38s |
| e19ec4f 当轮定向测试 | 0 | 209 passed, 1 skipped, 1 warning in 20.34s |
| e19ec4f 当轮全量测试 | 0 | 897 passed, 3 skipped, 3 warnings in 28.19s |
| `uv run ruff check .` | 0 | All checks passed |
| `uv run ruff format --check .` | 0 | 213 files already formatted |
| `uv run python scripts/check_secrets.py` | 0 | 无发现 |
| `git diff --check` / `git diff --cached --check` | 0 | 无空白错误，冲突已解决 |
| 12 案例 benchmark / baseline diff | 0 / 0 | baseline 无变化 |
| 完整 installed-wheel smoke | 0 | 新构建 wheel 与独立 sdist 重建 wheel 各 10 项 PASS |
| 独立文档身份与冻结边界检查 | 完成 | 8 份文档及 mapping 本地链接可解析，15 份冻结文档未变 |
| 独立运行契约复查 | 完成 | INT-01 修复并复验，无其他已确认重要问题 |

e19ec4f 当轮定向与安装命令（最新 R1 结果见上节）：

```text
uv run pytest tests/test_runtime_repair_integration.py tests/test_run_single_flight.py tests/test_runs.py tests/test_api_security.py tests/test_cli_multi_agent.py tests/test_required_output_validity.py tests/test_cli.py tests/test_prompts.py tests/test_handoff_validator.py -v
uv run specflow benchmark --suite benchmarks/cases --repo benchmarks/fixtures/portfolio-python --output artifacts/integration-20260913 --baseline artifacts/integration-20260913/baseline.json
git diff --no-index --exit-code benchmarks/results/mock-baseline.json artifacts/integration-20260913/baseline.json
uv run python scripts/smoke_installed_wheel.py
```

安装脚本自动按 uv.lock 导出约束，清除运行子进程的 PYTHONPATH/PYTHONHOME/provider 环境，确认 venv/site-packages 中非 editable 的 1.1.1 包。两轮均覆盖默认/显式 legacy、multi-agent、API mock、资源身份、custom/hostile CWD prompt 隔离。

- 两份运行时 wheel 的 SHA-256 均为 `d5ea0ba7f6b642dd6f77d0d6959d8359a28569dfb7ec966156d8464dc8314e0b`。
- 被独立重建的 sdist SHA-256 为 `cad139929667fae06f9ed399f8c319c8e967f8b47acfb4643e75ba58db6b4792`。
- 上述两行构建身份属于 e19ec4f 当轮，使用该轮运行时代码、收尾报告写入前的树；它们是验证产物，不是已发布版本。

没有新增 skip。3 个既有 Windows symlink skip 与 3 个 pytest warnings（两个 class 收集警告、Starlette/httpx 弃用警告）均保留。Ruff 首次检查报告既有 test_coordinator.py:113 的 invalid noqa 警告；Git 有既有 LF→CRLF 提示，未为消除提示修改配置。

日志副本：`C:/Users/50469/temp/specflow-integration-20260913-evidence`。

## 交付边界与后续决定

- 本地集成保留五个来源 PR 的历史、全部规范/学习材料，以及明确的集成调整。
- 相对 main 的大部分文件增量来自已经发布的来源 PR 文档，不是本轮重新生成的学习记录或新功能。
- 当前没有集成分支的远端 CI；各来源 PR 的历史 CI 不能冒充本次组合 CI。
- 所有远端输入在收尾检查时仍等于固定提交，原工作区保持不变。
- 后续应评审该本地候选，决定发布集成 PR/实际合并顺序，再依据合并后的验证关闭相应任务。当前不自动关闭 T-070，也不开始 T-071 或 M10。
