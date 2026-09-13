# 并行修复契约协调与隔离集成报告

日期：2026-09-13。状态：**本地集成验证通过，待审查候选**。

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
- 当前状态：**fixed，已有独立复验证据**。没有遗留的已确认阻塞发现。

独立复查产物：`C:/Users/50469/temp/integration-handoff-recheck-ze_jn708`。
这不等同于 GitHub 正式 APPROVE 或整个 M9/M10 已验收。

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
| 最终定向测试 | 0 | 209 passed, 1 skipped, 1 warning in 20.34s |
| `uv run pytest -v` | 0 | 897 passed, 3 skipped, 3 warnings in 28.19s |
| `uv run ruff check .` | 0 | All checks passed |
| `uv run ruff format --check .` | 0 | 213 files already formatted |
| `uv run python scripts/check_secrets.py` | 0 | 无发现 |
| `git diff --check` / `git diff --cached --check` | 0 | 无空白错误，冲突已解决 |
| 12 案例 benchmark / baseline diff | 0 / 0 | baseline 无变化 |
| 完整 installed-wheel smoke | 0 | 新构建 wheel 与独立 sdist 重建 wheel 各 10 项 PASS |
| 独立文档身份与冻结边界检查 | 完成 | 8 份文档及 mapping 本地链接可解析，15 份冻结文档未变 |
| 独立运行契约复查 | 完成 | INT-01 修复并复验，无其他已确认重要问题 |

最终定向与安装命令：

```text
uv run pytest tests/test_runtime_repair_integration.py tests/test_run_single_flight.py tests/test_runs.py tests/test_api_security.py tests/test_cli_multi_agent.py tests/test_required_output_validity.py tests/test_cli.py tests/test_prompts.py tests/test_handoff_validator.py -v
uv run specflow benchmark --suite benchmarks/cases --repo benchmarks/fixtures/portfolio-python --output artifacts/integration-20260913 --baseline artifacts/integration-20260913/baseline.json
git diff --no-index --exit-code benchmarks/results/mock-baseline.json artifacts/integration-20260913/baseline.json
uv run python scripts/smoke_installed_wheel.py
```

安装脚本自动按 uv.lock 导出约束，清除运行子进程的 PYTHONPATH/PYTHONHOME/provider 环境，确认 venv/site-packages 中非 editable 的 1.1.1 包。两轮均覆盖默认/显式 legacy、multi-agent、API mock、资源身份、custom/hostile CWD prompt 隔离。

- 两份运行时 wheel 的 SHA-256 均为 `d5ea0ba7f6b642dd6f77d0d6959d8359a28569dfb7ec966156d8464dc8314e0b`。
- 被独立重建的 sdist SHA-256 为 `cad139929667fae06f9ed399f8c319c8e967f8b47acfb4643e75ba58db6b4792`。
- 构建使用最终运行时代码、收尾报告写入前的树；它们是脚本生成并清理的验证产物，不是已发布版本。

没有新增 skip。3 个既有 Windows symlink skip 与 3 个 pytest warnings（两个 class 收集警告、Starlette/httpx 弃用警告）均保留。Ruff 首次检查报告既有 test_coordinator.py:113 的 invalid noqa 警告；Git 有既有 LF→CRLF 提示，未为消除提示修改配置。

日志副本：`C:/Users/50469/temp/specflow-integration-20260913-evidence`。

## 交付边界与后续决定

- 本地集成保留五个来源 PR 的历史、全部规范/学习材料，以及明确的集成调整。
- 相对 main 的大部分文件增量来自已经发布的来源 PR 文档，不是本轮重新生成的学习记录或新功能。
- 当前没有集成分支的远端 CI；各来源 PR 的历史 CI 不能冒充本次组合 CI。
- 所有远端输入在收尾检查时仍等于固定提交，原工作区保持不变。
- 后续应评审该本地候选，决定发布集成 PR/实际合并顺序，再依据合并后的验证关闭相应任务。当前不自动关闭 T-070，也不开始 T-071 或 M10。
