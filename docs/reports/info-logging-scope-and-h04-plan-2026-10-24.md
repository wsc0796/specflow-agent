# 两项 INFO 观测合同收尾与 H04 实验准备

日期：2026-10-24。基线：9586db1。范围见[任务](../tasks/info-logging-scope-and-h04-plan-2026-10-24.md)。

## 已完成

两项旧 provider-resilience 用例在全局 INFO 下均复现失败：HTTPX 请求日志包含普通配置端点，被原先合并所有日志的断言当作禁止公开内容。观察到的是测试端点，不是凭据泄漏。

本次只修改这两项测试及文档，不改生产日志行为。两项各参数化 WARNING/INFO，分别检查：

- 公开快照、异常安全文本、CLI stdout/stderr、原生产物和 specflow 自有日志不得出现配置端点。
- 全部捕获日志和上述输出不得包含测试凭据、其指纹、内部资源指纹或特定异常正文标记；原有模型标识断言保留。
- INFO 变体必须确实捕获 HTTPX 含普通端点的请求日志，不能通过关日志使检查失去意义。
- 为429响应注入带合成凭据的正文标记，检查其未进入观测输出。保留原有熔断次数、共享guard、退出码和错误分类断言。

这使测试与已接受的产品合同一致，不提供“第三方所有日志隐藏URL”的保证。仅对这些被测路径作结论。

## 验证证据

日志根目录：`D:\Documents\spec agent\outputs\info-h04-goal-20261024`。

| 检查 | 实际结果 |
|---|---|
| 修复前两项旧用例，全局 INFO | 2 failed；info-red.log |
| Provider resilience + H04 + F03，全局 INFO | 98 passed；focused-info.log |
| 产品全量，默认运行口径 | 1112 passed、3 skipped、3 warnings，31.43秒；pytest-full.log |
| uv run --no-sync ruff check . | 通过；ruff-check.log |
| uv run --no-sync ruff format --check . | 通过，222 files already formatted；ruff-format.log |
| H04离线请求预检 | 12份唯一请求、36试次计划；真实调用0；h04-preflight.log |

两项用例各增加一个日志级别变体，故全量相对1110增加2，不是新增两种产品能力。跳过仍为Windows符号链接权限，警告沿用既有测试类收集及TestClient依赖警告。测试通过既有Python依赖运行，入口核验导入来自本工作区，测试进程移除继承的供应商配置并保留真实HTTP阻断。

关键命令（用既有环境执行，不安装依赖）：

```powershell
$env:UV_PROJECT_ENVIRONMENT = 'C:\Users\50469\specflow-future-tasks-review-20260913\.venv'
uv run --no-sync python -B 'D:\Documents\spec agent\outputs\h04-f03-offline-20261023\run_offline_checks.py' 'C:\Users\50469\specflow-h04-f03-20261023' -v
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
```

全量已覆盖两项WARNING/INFO参数化；98项聚焦是全局INFO口径，不将其说成整套全量INFO验证。

## H04 下一阶段材料

本地目录：`D:\Documents\spec agent\outputs\info-h04-goal-20261024\h04-plan`。

- `GOAL.md`：六个案例、人工与结构判据、预算、停止条件、后续执行指令。
- `cases.json`：六例合成输入及18份语义评分校准材料，未使用Holdout。
- `preflight.py`：仅离线，复用实际输入投影和AgentRunner构造消息，无真实Provider/live开关。
- `preview-01/request-plan.jsonl`、`blind-grading.csv`、`preflight.json`：36次NOT_RUN计划、144条待判项和预检结果。

已验证组间仅反馈段不同；需求和仓库分析完整在请求中，未被500字符摘要裁切；反馈JSON完整相等。24项结构控制通过，故意语义错误的材料仍能通过Schema，说明语义评分不能被结构检查替代。独立人工校准尚待完成。

真实实验预算提案：6例×2组×3重复=36次目标请求，单次输入≤4096、输出额度2048 Token，默认零重试、并发1，提议费用上限10元。模型/端点/价目/适用Tokenizer待用户确认后冻结；Token配置额度不当作通用计费上界。

现在没有真实执行器，也没有真实模型结果。后续Goal先完成受限执行器及离线预算门禁、人工校准，再展示最终配置请用户确认；用户确认前禁止发出第一个真实请求。compact不接入，产品src未修改。

## 结论与交付边界

两项旧INFO问题按已接受的合同完成收尾；H04真实对照已形成可审阅执行材料，仍为NOT_RUN。可以描述诊断边界与评测准备，不可新增真实纠错收益表述。此前压缩包和旧日志保持原样，不能把旧包当成本次提交版本。
