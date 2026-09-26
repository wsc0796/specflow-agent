# 2026-09-26 集成修复统一验证 — T-082 至 T-086

- 工作区：`D:\Documents\ChatGPT\一个月冲刺\specflow-agent`，使用保存项目的本地checkout。
- 基线：09bd60d8a189367c0ac443028e9b4ee3b33139f7；分支：codex/t082-t086-integration-repairs。
- 授权：用户要求检查已指出的集成问题，若存在由主窗口修复；5项均按独立规格顺序实施。
- 当前状态：COMPLETE；五项各自RED→GREEN，最终全量/静态检查通过，独立审查无新增问题。

## 持久交付与证据

| finding | task / 报告 | 本地提交 | 实际针对性证据 |
| --- | --- | --- | --- |
| F5 CLI额度入口 | [T-082](T-082-cli-llm-call-budget-report.md) | 4b98ec7 | RED 2failed/6passed → 67相关passed |
| F1 输入字段交付 | [T-083](T-083-preserve-agent-input-fields-report.md) | 1121ddb | RED 6failed → 91相关passed |
| F2 来源快照一致 | [T-084](T-084-evidence-snapshot-consistency-report.md) | 6db31a8 | RED 6failed → 93passed/1skip；新增边界后focused7passed |
| F3 Evidence deadline | [T-085](T-085-evidence-shared-deadline-report.md) | fb3b097 | RED 8failed/1passed → 143passed/1skip |
| F4 成功Trace状态 | [T-086](T-086-accepted-agent-trace-status-report.md) | 引入本报告的提交 | RED 2failed/1passed → 76相关passed |

每项规格均通过adaptive-sdd结构/追溯检查；既有目录惯例保留为单task spec，临时视图只用于校验。
各自报告记录验收结果和`git revert <对应提交>`回退；本报告汇总五项最终全量，不复用历史866结果。

## 测试隔离与原材料保护

本批证据/备份根：
`D:\Documents\ChatGPT\一个月冲刺\specflow-repair-backups\2026-09-26-integration-audit-T082-T086`。
启动时17个dirty文档/Word原样备份并核对；index为空，源码与交接基线一致，T082–T086编号未占用。
raw attempts保留原地及此前明确路径局部备份，没有遍历或读取正式数据。

沿用核对后的validate.py/child_guard.py：导入前删除全部SPECFLOW_LLM_*，断言不存在；同步/异步
真实HTTPTransport阻断计数。子进程仅已核对Git/Windows版本查询及临时Mock worker入口，传入无凭证
环境；worker独立HTTP哨兵报告由父进程复核。未读取凭证，不改持久环境，uv --offline不当作网络沙箱。
每次测试用新标签/新basetemp，原T078–T081与正式Dev/Holdout/旧基准不覆盖。

运行命令前缀：`uv run --offline --no-sync python -B -X utf8 <证据根>/validate.py`。
每项报告中的标签对应同名`.log`、`-isolation.json`与`-artifacts/`；全量参数仅`integration-full -v`。

## 最终验证与审查

2026-09-26 最终全量：**899 passed、3 skipped、3 warnings，84.60s，exit=0**。
新增33个测试用例，原测试没有删除、弱化或新增skip/xfail。3个skip仍为Windows符号链接权限限制；
warnings仍为TestStrategyAgent/TestStrategyOutput收集提示与Starlette TestClient/httpx弃用提示。
实际主HTTP=0、子HTTP=0，1个临时Mock worker，246个已清理环境的子进程。
`uv run --offline --no-sync ruff check .` 与 `ruff format --check .` exit=0（225文件），diff检查通过。
T-086单行补丁的换行格式已归一；格式化前后无语义差异，不重复运行全量。

独立只读review_t078审查本批全部产品diff、规格、新测试与调用方，结论通过，无Critical/Important/Minor。
重点核查CLI/Legacy参数、实际输入交付与估算预算、快照定义与版本拒绝、ToolExecutor外的deadline传播、
未知计数省略、Trace默认值兼容和冷导入。实际执行结果由本任务的全量与隔离记录提供。
reviewer考虑后留在规格边界之外的事项：估算与真实计费差异、脱敏前/未读尾部/采集后文件变化、同步
操作强杀、Legacy共享deadline、正式任务质量和learner ownership；均按下节残余边界保留，不扩修。

交付只含本批规格列出的代码/测试/README与报告；17个启动时dirty材料保持原样、不暂存。
原Day10/11 attempts、正式Holdout、旧Mock基准与评分结果没有修改或重跑。最终提交按精确路径核对。
最后一项提交的确定性定位：

```powershell
git log -1 --diff-filter=A --format=%H -- docs/reports/T-086-accepted-agent-trace-status-report.md
```

## 残余边界

- 显式调用额度不保证业务Review通过或任务语义成功；默认仍10，正常12请求和单轮revision15需显式额度。
- 完整输入以现有4字符/token估算控制；真实usage仍独立核算，不能声称估算就是Provider计费硬界。
- hash覆盖完整有界脱敏读内容；截断文件尾部未读，不是原始全文件或跨文件事务快照。冲突路径明确剔除。
- 单次同步工具不能强杀；deadline阻止下一次派发，失败后保存已返回工具数，其它未完成统计不伪装为0。
- 原Day14越界、learner PARTIAL保持；本次Fake结果不能作为正式task_success提升证据。

只本地提交，不推送、发布、创建PR或追加Memory/Vector/Tool平台。
