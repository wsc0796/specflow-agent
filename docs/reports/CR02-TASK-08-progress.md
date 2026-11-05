# CR02 TASK-08：进度与恢复入口

任务启动：2026-11-02；最新更新：2026-11-03（Asia/Shanghai）。基线：`a7b6f64291d0ffdb4d15f59af9c5c6ed96fb73d2`。
状态：**TASK-08 工程实现、独立审查及最终全库门禁完成，2026-11-03 本地聚焦交付。**
本次用户已明确要求完成 TASK-08，沿用 [任务单](../tasks/CR02-TASK-08.md)，不再按旧计划后移。

## 当前任务进度核对

| 任务 | 核实状态与证据 |
| --- | --- |
| TASK-00 | 实施接点核定已完成；不是产品验收。[核查记录](CR02-TASK-00-completion.md) |
| TASK-01 | 六例早期材料和先导准备已交付；24 例全量材料/语义未完成。[早期切片](CR02-TASK-01-early-slice.md)、[先导准备](CR02-SIX-CASE-PILOT-READINESS-2026-11-02.md) |
| TASK-02 | 持久受理与执行纵向切片已实现，底座已有运行证据；其完整总验收未关闭。[进度](CR02-TASK-02-progress.md) |
| TASK-03 | 规则、完整协议与外部核验闭环已有工程交付；不代表业务语义全通过。[完成记录](CR02-TASK-03-completion.md) |
| TASK-04 | 动态取证、一级顺序委派及 Provider 适配已离线交付。[完成记录](CR02-TASK-04-completion.md) |
| TASK-05 | 人工检查点/修订已实现并经独立审查修复。[完成记录](CR02-TASK-05-completion.md) |
| TASK-06 | 条件项目记忆已实现并经独立审查及离线门禁。[完成记录](CR02-TASK-06-completion.md) |
| TASK-07 | 可读报告、查询和薄 CLI 已实现并经独立审查及离线门禁。[完成记录](CR02-TASK-07-completion.md) |
| IMPACT-01 | 候选影响发现/显式采用已离线交付并审查关闭，本轮不重开。[完成记录](CR02-TASK-IMPACT-01-completion.md) |
| TASK-08 | 本轮已完成显式 fresh/reuse retry API/CLI、有效前缀与完整委派复用、fallback、来源/预算/权限及故障验证；两个实质问题已修复并同轮复核关闭，最终1683 passed/3 skipped/3 warnings。[完成记录](CR02-TASK-08-completion.md) |
| TASK-09 | 完整分层验收/演示/价值记录未完成；F01 两次真实失败保留，v3 只有离线准备。[下一试验卡](CR02-F01-V3-NEXT-TRIAL-CARD-2026-11-02.md) |
| TASK-W01～03 | 条件写入尚未实施，当前 write 仍固定关闭；不因 TASK-08 回放完成而获得写入或副作用重放能力。 |
| 简历双条 | 两条工程参与表述已由 Astra 验收并本地提交 a7b6f64；不替代以上未完成项。[报告](CR02-RESUME-PAIR-2026-11-02.md) |

## 实现决定与验证环境

- 同输入 retry 不使用 enqueue_revision，避免生成新 input 或改变原规则/配置。
- 用新 attempt 的 replay binding 关联旧完整记录，不伪造物理 call；子结果稳定句柄经当前归属 resolver 引入。
- v2 显式 profile 开启 replay；v1 默认指纹不变，支持 COMMON fresh。
- 本地 `.venv/Scripts/python.exe` 已核对为 Python 3.12.10、pytest 8.4.2，现有依赖可导入。
- 用户 `CR02-CURRENT.md` 仍为原有 20 insertions / 7 deletions，未修改、未纳入交付。
- 本轮上下文监督结果 healthy。只读 code-scout 已完成接点核对，未修改源码或执行测试。

## 最终实现与验证

新增 retries.py/replay.py，接入严格 retry API/CLI、同输入新 attempt、顺序前缀与完整子结果 binding；
追加 schema v7，保留原迁移/checksum。Records 只持 Store，Session 仅注入 records/fence/context，
仍用原业务循环和真实 I/O 门禁。源码在最终门禁期间及之后保持冻结。

最终命令：`uv run --offline --no-sync pytest -v -s --tb=short -p no:cacheprovider`。
实际 **1683 passed / 0 failed / 3 skipped / 3 warnings，2110.23s，exit0，收集1686项**。
三项skip均为Windows符号链接权限；警告是Starlette/httpx弃用和两个TestStrategy类收集提示。
全库 Ruff check / format --check（296 files）及差异检查通过。

同一独立 `/root/task08_astra_review`（显式 gpt-6-astra/xhigh、fork none）已关闭前序漏检F01
和显式材料消费误拒补充项，最终总体PASS、blocking_findings=[]。
各项真实红灯、定向绿灯、旧迁移版本期望修复及ABORTED/exit1记录分别保留，未拼接为一次通过。

六份fresh/reuse对照均来自最终完整通过的pytest-229，实际源码build已核对一致：
工具后故障3模型/1工具→2模型/0工具；完整前缀或完整委派可0新派发；父验收未保存不复用。
它们是受控降级报告的程序结果，不是业务语义或生产费用收益。

完成/接口/正文：[完成记录](CR02-TASK-08-completion.md)。
独立身份和问题关闭：[Astra记录](CR02-TASK-08-ASTRA-REVIEW-2026-11-02.md)。
最终日志/原始对照与历史：[证据索引](evidence/CR02-task08-2026-11-02/evidence-index.json)。

本地聚焦交付仅含本任务实现、直接测试、文档和证据；重新核对清单并纳入最后的材料消费修复。
用户CR02-CURRENT.md原有改动保留并排除；固定提交SHA随最终交付提供，不推送。

## 后续未完成项

TASK-01材料全量、TASK-02总验收正式收口、TASK-09业务语义/价值验收及条件写入分别保留状态。
E03原完整场景缺证、F01两次真实失败/v3未跑均未被TASK-08覆盖；不自动启动收费试验或旧automation。
