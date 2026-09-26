# T-082 完成报告 — CLI 调用预算（F5）

- 日期：2026-09-26；规格：[T-082](../tasks/T-082-cli-llm-call-budget.md)。
- 状态：本项实现和相关回归完成；最终五项全量结果见本轮统一验证报告。

新增 `run --max-llm-calls`，只允许正整数及 Multi-Agent；显式参数创建单次 policy，不改变默认10。
README 实时例子配置12，并说明包含单轮 revision 的完整路径需要15次额度。Legacy 显式使用该参数
在调用 runner 前拒绝，exit=2。没有真实 Provider 请求。

| AC | 状态 | 实际证据 |
| --- | --- | --- |
| AC-001 | PASS | test_cli_budget_controls_actual_provider_requests：12→exit0/12次；10与省略→exit3/10次，manifest CALL_BUDGET_EXCEEDED |
| AC-002 | PASS | 0/-1/1.5/abc 和 Legacy 参数都在执行前 exit2；相关 CLI/请求预算回归通过 |

隔离包装位于 `D:\Documents\ChatGPT\一个月冲刺\specflow-repair-backups\2026-09-26-integration-audit-T082-T086`。
命令前缀：`uv run --offline --no-sync python -B -X utf8 <该目录>/validate.py`。
`t082-red -v tests/test_cli_llm_call_budget.py`：2 failed、6 passed；显式参数尚不存在导致预期失败。
`t082-green -v tests/test_cli_llm_call_budget.py tests/test_cli.py tests/test_cli_multi_agent.py tests/test_multi_agent_request_budget.py`：
67 passed。真实 HTTP 尝试=0。Ruff/diff 通过；初次 lint 的行长度/import 排序已格式修正。
规格 plan/verify 结构追溯通过；原有断言未改删。

本项提交只含 cli.py、README、新测试、规格和报告。保持其它预算/Review/revision 合同；参数
提供额度不保证业务语义成功。回退 `git revert <引入本报告的提交>`；不推送/发布。
