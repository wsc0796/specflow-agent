# T-078 — Stage 校验失败的有界审计记录

- 版本：v1；2026-09-25；状态：FROZEN / approved-for-execution。
- 基线：`18690677f8c18a53a39a495eeaafa53c624ffb1a`。
- 分支：`codex/t078-stage-failure-observability`，保存项目的本地 checkout。
- 授权：用户阅读 P15-REPAIR-v1 后明确要求“新开一个窗口进行修复”。
  本修复任务是第一批唯一写入入口，取代计划中的旧教学任务写入入口。
  计划 PROPOSED 是授权前快照；本授权允许直接进入 PATCH。
- learner diagnosis：PARTIAL；执行、AI 审查、测试通过不计本人掌握证据。
- 来源：[修复计划](../study/day-15-safe-repair-plan.md)、
  [F15-01](../study/evidence/day-15-f15-01-observation.md)。

## 目标与范围

只修 scheduler 已返回结果而 stage 校验拒绝时，具体失败信息未进入失败 Artifact 的缺口。
已有可执行方案，采用局部任务契约，不重新启动需求发现或完整架构设计。

允许的产品改动只有 `src/specflow/runner_multi.py`；新增测试只有
`tests/test_multi_agent_failure_observability.py`。文档为本规格、
`docs/reports/T-078-stage-failure-observability-report.md`，以及必要 Day15 状态同步
（CURRENT、execution card、learner review、Retest Queue v2）。原有材料保留且不混入提交。

禁止修改 scheduler、Provider、Schema、Evaluator、Prompt、预算/retry/revision 行为、依赖；
禁止真实 Provider、正式 Dev/Holdout 运行、读取 Holdout 题面/Gold/output，以及 Vector、Embedding、
Hybrid、Rerank。不得移动 `results.append` 或 `prior_outputs.update` 越过校验边界。

## 实现上下文与冻结合同

`run_multi_agent → _run_and_accumulate → scheduler.execute → _validate_stage_results`
是本批链路。scheduler map key 和 runner 赋予的 stage_index 是身份真相源；role/version
取 registry，返回 envelope 自报身份不可信。`stages`、`prior_outputs` 仅包含已接受结果。
校验拒绝用内部 ValueError 子类携带不可变、有界审计记录，顶层专门处理，保持
`manifest.error=MULTI_AGENT_RUN_FAILED`、failed / exit=3，不打印原异常或模型正文。

审计记录只保存一个触发拒绝的 agent（并行次序不保证），包含可信身份、stage、分类及来源，
可用 scheduler 时间。时间缺失用 null；不采集返回体 usage，不把未知 Token 伪装为 0。
仅原 ErrorCode 枚举和 adapter 的 `SCHEMA_REGISTRY_UNAVAILABLE`、`SCHEMA_NOT_FOUND`、
`AGENT_EXECUTION_FAILED` 可作为 executor 分类；未知/缺失/畸形值统一为
`AGENT_EXECUTION_FAILED`。本地非对象输出为 `AGENT_OUTPUT_NOT_OBJECT`。

拒绝优先级保持旧 gate 顺序：身份不符 → `AGENT_EXECUTION_FAILED / stage_validator`；
executor success 为 false → 允许表分类 / `executor_reported`；output 非对象或 Schema
拒绝 → 本地分类 / `stage_validator`。身份不符不采信自报错误。classification_source
说明谁报告错误，不宣称已证明历史 Provider 根因。

- manifest 可选 failure_context 精确含 kind=`stage_result_validation`、agent_id、
  stage_index（字符串）、error_code、classification_source。
- agent-outputs 在 `stage-{index}/{agent_id}` 增加 audit-only 摘要，含 agent_id、role、
  stage_index（数字）、success=false、schema_validated=false、degraded=true、audit_only=true、
  error_code、classification_source；不含 output/raw/message/usage。
- traces 增加同 run/coordinator 下的 failed agent span，stage 为数字，metadata 包含
  error_code、classification_source 和审计来源；只使用 scheduler 时间，不冒充 Provider trace。
  既有 Handoff failure_context 原样兼容，成功路径不加失败字段。
- 复用 `_safe_write` 和 `_finalize_run_directory`；写盘/超限仍失败，不能虚构 `_COMPLETE`。

接口预检：失败记录只由 validator 产生、专用异常传递、persist 消费；不得进入已接受 stage
或下游 input/handoff。顶层与 persist 的新参数为可选参数，旧 Handoff 调用兼容。
调度器抛错、超时、结果返回前预算拒绝没有该对象，保留旧路径，不虚构 agent 记录。

## 验收与验证映射

| AC | 证据要求 |
| --- | --- |
| AC-01 | F15-01 同类新合成运行 RED→GREEN；failed/exit=3、specialists=0、stages_completed=0 |
| AC-02 | FakeLLMClient + 真实 AgentRunner 分别非法 JSON/Schema；保留 executor 分类，调用一次 |
| AC-03 | success=true 但 Schema/非对象输出/身份不符；本地分类、无正文、下游未运行 |
| AC-04 | Stage1 失败仍保留已接受 Stage0；只计 1 stage，Synthesis/Review 不运行 |
| AC-05 | 分类缺失/未知/畸形、伪身份、合成 secret/绝对路径/超长正文不透传；摘要固定有界 |
| AC-06 | 既有六 Agent 成功、真实下游 input/handoff 与调用次数保持 |
| AC-07 | 既有零 Evidence/Handoff integrity/预算/单轮 revision 回归；不新增 skip/xfail |
| AC-08 | 写盘故障与 artifact 上限；非成功退出，无虚假完整标记 |
| AC-09 | manifest/output/trace 的 agent/stage/code/source 一致；失败记录不污染接受集合和下游 |
| AC-10 | 测试进程先删除全部 SPECFLOW_LLM_*；真实 HTTPTransport 哨兵计数=0；子进程无凭证 |

先修前相关回归，再新增 focused 测试确认 RED，随后最小补丁、focused GREEN、相关回归，
最后一次必要全量 `pytest -v`，Ruff check/format 与 diff 检查。全部通过隔离 Python 包装运行，
先删除环境键再导入项目；阻断/计数真实同步及异步 HTTPTransport，MockTransport 仍可用。
子进程只允许已核实测试所需的临时仓库 Git 操作，删除继承 SPECFLOW_LLM_* 后启动。
不修改持久环境；包装不声称是 OS 网络沙箱。

相关回归：test_cli_multi_agent、test_agent_adapter、test_scheduler、test_execution_policy、
test_runs、test_fallback、test_cli。完整 pytest 只执行现有合成/Mock 测试，不运行 benchmark。
既有 812 passed 是历史值，必须记录新输出。

## 保护、计划检查与收口

启动核对 HEAD/branch/status/index 与计划一致；T-078 未占用、index 为空。
局部备份：`D:\Documents\ChatGPT\一个月冲刺\specflow-repair-backups\2026-09-25-160657-T078`。
保存 tracked diff、已有全部未跟踪文档/Word，以及两个明确 raw attempts 路径；447 文件、
1880456 字节，4 个指定学习文档/raw JSON 样本逐字节比对一致。原件未移动。

实施授权与 learner gate 分开；不等待教学回答，learner PARTIAL 保留。
批准方案能在 1 个产品文件内完成；范围、消费者兼容、失败顺序和测试映射已检查。
遇到意外网络/正式数据访问/并发改动，或需要扩大产品范围时停止，不自动启动下一批。

完成后记录新实验 Artifact 前后差异、实际命令/退出码、独立代码审查、unknown 和回退。
仅逐路径暂存本批产品、测试、规格、报告；必要状态同步保留在工作区，避免带入历史材料。
不推送、不发布、不创建 PR。提交后 `git revert <本修复提交>`；未提交时保存修复 diff 后
仅逆向应用本批补丁，不覆盖历史 dirty 材料。Day14 越界报告保留，不视为获用户豁免。

## 验证环境勘误（2026-09-25）

冻结需求和产品范围不变。验证发现 Python 标准库可能执行 Windows `ver` 查询，且现有
`test_child_receives_no_annotations_and_records_actual_messages` 经 `launch_worker` 间接启动
一个临时合成 Mock worker；原“子进程只允许 Git”预检不完整。精确允许这两种已核对入口，
worker 必须处于本次 basetemp、provider=mock/mode=legacy，且使用导入前环境断言和真实
HTTPTransport 阻断/计数包装；父进程核对其独立报告。详见完成报告的失败记录及裁决。
不能将这个例外用于正式 Dev、其他 Python 子进程或真实 Provider。
