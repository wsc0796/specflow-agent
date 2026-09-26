# T-079 — 请求预算与剩余时间修复报告

- 日期：2026-09-26；状态：COMPLETE；最终全量通过，独立审查问题已修复，仅本地聚焦提交。
- 规格：[T-079](../tasks/T-079-llm-budget-boundary.md)；基线 `633a941e3ff81a22282ea4fbd60576ac026f9956`。
- 分支：`codex/t079-llm-budget-boundary`，原本地 checkout。用户明确批准必要修复；没有创建 worktree。

## 实际行为

Coordinator enrichment 与 Agent 的实际 LLM complete 共享请求预算。请求前原子检查调用数和
已观测 Token 剩余量，为并发在途请求预留输出额度，调整 max_tokens；响应一到达就在解析业务
JSON/Schema 前记录 usage。解析失败不再丢掉已知用量，usage 不可得保持未知并阻止后续请求。
政策异常穿过 adapter/enricher 到 runner，不再伪装成普通 Provider 错误或继续降级。

调用前后检查共同 deadline，可选请求 timeout 取当前剩余时间与已有更小限额，真实 HTTP client
再取配置与请求的较小值；迟到结果不能作为已接受 stage 输出。scheduler 等待已启动线程退出
的合同不变，没有线程强杀、后台游离任务或新增取消 API，也没有增加重试。

失败 manifest 新增 budget_usage：实际请求数、已观测输入/输出 Token、小计覆盖和未知次数。
成功总 metrics 包含 Coordinator；分 Agent metrics 保持分 Agent 口径，二者不要求求和相同。
Observer 在预算包装内，看到真正发送的 messages/max_tokens；LLMRequest 新 timeout 不放进 HTTP JSON。
Observer 可能同步阻塞，因此调用/输出额度先预留，在回调返回后重新检查 deadline/粘滞失败，
刷新 timeout 后才计实际发送次数。回调后的拒绝会释放预留，实际调用计数不增加。
Observer 是发送前观察，出现回调后拒绝时观察条目不等于实际发送证明；实际数量以 budget_usage 为准。
planning 在发请求前进入合法 PLANNING 状态，使该阶段失败能记录 PLANNING→FAILED。

明确的兼容变更：默认 cap=10 不变，真实完整链路 6 enrichment + 6 Agent 需要至少 12 次额度；
显式 cap=10 现在会阻止第 11 次请求。需要完整调用链的既有 Fake live 成功测试显式设置 12，
原有 12 次观察、6 Agent 和 Context 隔离断言全部保留。Mock 确定性 Agent 不再冒充 LLM 调用；
Mock 的 enrichment complete 仍计入预算。没有调整全局默认、Prompt、topology 或正式实验配置。

## 保护与执行记录

本地证据根：`D:\Documents\ChatGPT\一个月冲刺\specflow-repair-backups\2026-09-26-093911-T079`。
`inventory.json`、`tracked.diff`、`files/` 保存开始时所有 dirty 学习材料，复制后逐字节核对。
Day10/Day11 原始 attempts 保留原地，已有 T-078 局部备份继续有效；本次没有改动这些路径。
沿用经核对的 `validate.py` 与 `child_guard.py`：导入前删除全部 SPECFLOW_LLM_*，主/子真实
HTTPTransport 阻断计数，只有临时 Mock worker 可以通过已限定入口启动；不读取凭证或正式数据。

通用验证命令：

```powershell
uv run --offline --no-sync python -X utf8 '<本地证据根>/validate.py' <标签> -v <测试文件>
```

每个标签使用新 basetemp，不覆盖前次 Artifact；日志、isolation JSON 和 Artifact 保存在证据根。

| 标签 | 结果 | 说明 |
| --- | --- | --- |
| plan-check 初次 | 2 errors / 2 warnings | 规格使用 REQ/AC 范围缩写，确定性 validator 不展开；改成逐项 ID 后重跑 |
| plan-check 修正 | 0 errors / 0 warnings | 根据本规格 Specification/Design/Tasks 生成临时视图验证，正文是持久真相源 |
| red | 23 failed，exit=1；HTTP=0 | cap 不生效、失败 usage 缺失，以及新接口尚不存在；无产品改动时运行 |
| green | collection error，exit=2；HTTP=0 | enricher 模块级导入 policy.models 与既有 plan.hash_utils 初始化构成循环 |
| green-fixed | 23 passed，exit=0；HTTP=0 | 在 enrich 调用内导入 SpecFlowError，保持范围内解决；新测试 lint 也修正 |
| related 初次 | exit=4，0 collected；HTTP=0 | 测试文件名误写 test_plan_enricher.py，实际为 test_semantic_enricher.py；修正命令后重跑 |
| related-fixed | 203 passed、1 skipped、1 warning，exit=0；HTTP=0 | 11 个相关测试文件，包含 T-078 与 Provider/计划层 |
| observer-red | 3 failed、23 deselected，exit=1；HTTP=0 | 独立审查反例：Observer 耗尽 deadline 仍发送；另外两个新回调边界接口尚不存在 |
| observer-green | 206 passed、1 skipped、1 warning，exit=0；HTTP=0 | 修复审查问题后，26 项新测试与全部相关回归通过 |
| full | 856 passed、2 failed、3 skipped、3 warnings，exit=1；父/子 HTTP=0 | 冷启动循环导入与旧 Mock 计量快照暴露不兼容 |
| full-failures | collection error，exit=4；HTTP=0 | 单独重测触发 policy.models→plan.models→agents→adapter 的循环，明确冷启动根因 |
| compatibility-green | 28 passed，exit=0；父/子 HTTP=0 | 原两条失败用例与26项新测试通过；冷启动Mock worker实际执行成功 |
| full-fixed | 858 passed、3 skipped、3 warnings，exit=0，115.17s；父/子 HTTP=0 | 最终全量；246 个子进程经环境清理，1 个临时合成 Mock worker |

最终 `uv run --offline --no-sync ruff check .`、`ruff format --check .` 均 exit=0，219 文件格式通过；
`git diff --check` 通过。3 个 skip 均为既有 Windows symlink 权限限制；3 个 warning 为既有
TestStrategyAgent/TestStrategyOutput 收集提示与 Starlette TestClient/httpx 弃用提示。
没有新增 skip/xfail，没有改删旧断言；一次全量失败后因实际兼容修复才执行必要复跑。

## AC 证据映射

| AC | 核验方式 | 当前状态 |
| --- | --- | --- |
| AC-001 | cap=1/3/10 都严格拦截；12 请求成功；并发 max_tokens=8/2 共预留10；超额响应后禁止新调用 | PASS |
| AC-002 | 非法业务 JSON/Schema 的第7次 usage 保留；缺失/float/bool usage 明确未知；adapter 政策传播；Provider 原异常保持 | PASS |
| AC-003 | 可控时钟 deadline=110：timeout 10→2，迟到响应拒绝且计量保留；MockTransport 检查 timeout=min(配置,请求) | PASS |
| AC-004 | 206 相关回归、最终858全量、Ruff/diff通过；独立审查问题RED→GREEN；原材料保留、逐路径本地提交 | PASS |
| AC-005 | 旧 Mock 基准保留，新版本 JSON 全量比较；临时 worker 冷启动成功 | PASS |

上述针对性证据均在 `tests/test_multi_agent_request_budget.py`，现有 T-078/成功/Handoff/预算/
revision、adapter、coordinator/enricher、Provider、Run API 回归共同验证兼容性。

## 独立审查及修复

只读 reviewer 确认 1 个 Important：Observer 内可能等锁/写盘，初次实现把最终 deadline 检查放在
Observer 之前，故回调耗尽时间后仍会发送。没有 Critical/Minor。按 REQ-003 补三条反例：
`test_slow_observer_cannot_send_after_deadline`（真实 runner 接线）、
`test_observer_delay_is_deducted_before_http_send`、
`test_sibling_failure_cancels_request_waiting_in_observer`。
观察 RED 后，把最终发送检查/实际计数移到回调后；未发请求释放预留。

审查范围裁决：未知输入预估、已发送请求撤回、线程强杀保持规格排除；Provider 协议层不可解析时
usage 保持 unknown；非政策 planning 异常的全面审计不扩修。代价是这些既有限制仍存在，不能据本次
测试声称严格计费硬上限、任意线程即时终止或历史失败已定位。未用这些限制豁免发现的 Observer 问题。

全量发现的必要兼容处理：adapter 的政策类型导入也改为 execute 内执行，解决冷启动循环；
新增 `benchmarks/results/mock-baseline-request-budget-v1.json`，仅输入/输出 Token 总量与旧
快照不同（0/0→3672/1800），其余 JSON 完全相同。对应测试仅更新比较路径，仍完整比较 JSON。
旧 Mock 快照保留原样；REQ-005/AC-005 在修改前补入冻结规格，不调整任何正式数据或评分器。

## 实际 Artifact 对照

同一 Fake 输入、显式 cap=12 的完整运行，新建临时目录进行修前/修后对照：

| 字段 | 修前 red Artifact | 修后 observer-green Artifact |
| --- | ---: | ---: |
| metrics.llm_call_count | 6 | 12 |
| metrics.input_tokens | 18 | 36 |
| metrics.output_tokens | 12 | 24 |
| metrics.total_tokens | 30 | 60 |
| budget_usage.usage_observed_calls | 字段缺失 | 12 |
| budget_usage.usage_unknown_calls | 字段缺失 | 0 |
| budget_usage.usage_complete | 字段缺失 | true |

实际 Fake 请求为 12 次，每次 input=3/output=2；旧统计只包含 6 个 Agent，新的总量包含
6 次 enrichment。数值增加代表统计修正，不代表增加了请求或费用。
证据根 `artifact-comparison.json` 保存精确 run 路径与摘录；原始完整性文件与 JSON 都保留。
失败解析场景测试另断言第 7 次返回 usage 后仍有 observed input=29/output=19、coverage=7/7；
缺失 usage 场景则为 observed=6、unknown=1、complete=false。

## 限制与回退

输出额度是请求准入与并发预留，不是 Provider 计费保证：真实输入 Token 只有响应后才知道，
Provider 可能不遵守请求 max_tokens，已发送请求不能撤回。已观测超额会保存并阻止后续调用；
缺失 usage 的 observed 小计不能当完整总成本。HTTP timeout 是 I/O 等待期限，任意同步 executor
仍不能被强杀；保持等待收口，避免 Run 结束后旧线程继续工作。默认重试仍为 0。

这些行为没有证明历史 Day11 Provider 根因或提高 task_success；没有跑正式 Dev/Holdout，
没有改写 Day14 越界记录，也不提升 learner PARTIAL。学习行政文件本批保持原样。
仅创建本地聚焦提交，不推送、不发布；回退用 `git revert <引入本报告的提交>`，无数据迁移。

17 个启动时 dirty 学习材料与本地副本逐字节一致；CURRENT、原 Day15 原文、Word、Day13/14
报告均未改动或暂存。只提交本批 6 个产品文件、3 个测试文件、1 个新 Mock 快照和2份规格/报告。
引入本报告的提交可用以下命令定位，避免在提交自身内容中写循环依赖 SHA：

```powershell
git log -1 --diff-filter=A --format=%H -- docs/reports/T-079-llm-budget-boundary-report.md
```
