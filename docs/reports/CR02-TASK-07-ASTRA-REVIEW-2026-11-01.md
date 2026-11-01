# TASK-07 Astra 独立审查与限定复核

日期：2026-11-01（Asia/Shanghai）。目录：`C:/Users/50469/specflow-h04-f03-20261023`。
审查基点：`f77cd7cfddf17883f669b3a669ce990fea5f6947`。

用户指定的独立代理 `/root/task07_astra_review` 以 `model=gpt-6-astra`、
`reasoning_effort=xhigh`、`fork_turns=none` 创建，读取原规格、任务单、恢复记录及当前差异
（含未跟踪的新模块和测试）。代理未修改仓库，未调用真实网络或读取实际服务凭据。

## 确认发现与修复

| 优先级 | 确认反例 | 修复 |
| --- | --- | --- |
| P2 事件归属元数据缺口仍显示完整 | 保留 event/review/seq/ref/hash，删除 body.job_id 或改错 body.input_revision_id；按正确 job 查询仍显示 complete、payload_available=true，详情200 | 对 job_id/input_revision_id/event_type 要求字段存在并匹配权威行列；缺失/不符标 event_metadata_unavailable/incomplete，详情按 EVENT_PAYLOAD_NOT_AVAILABLE 返回404。nullable 字段也不能用缺字段冒充 |
| P2 Markdown 遗漏覆盖来源引用 | 受控 adapter 提交合法单行 SourceRef，宿主校验/正式保存成功；JSON coverage.source_refs 有值，Markdown 没有该片段与 target 的关联 | 增加逐目标覆盖来源片段投影，完整保留 target_id 和全部 SourceRef；覆盖摘要表继续供快速阅读 |
| P2 无效服务端口导致 CLI 异常逃逸 | 固定假认证，--base-url http://localhost:notaport 通过原检查，httpx.InvalidURL 未捕获，实际抛栈 | 读取认证前验证 parsed.port 的语法及范围，并受控处理 InvalidURL，按参数错误退出2；没有网络派发 |

独立首轮为 **4 条反例失败，6.32 秒**，对应上述三项。主代理修复后定向回归
**16 passed / 36 deselected，13.01 秒**。该轮初次新测试遗漏 json import 的日志保留在
`specflow-cr07-review-fixes-20261101.log`；修正后为 `specflow-cr07-review-fixes-fixed-20261101.log`。
同一 CLI 输入错误分支另补过深 JSON 的受控失败，单项 **1 passed，0.59 秒**。

## 限定复核

同一 Astra 代理仅复跑原三项对应的四条接口/退出反例，结果 **4 passed，6.26 秒**，
明确确认 **三项 P2 全部关闭**，复核结束，没有展开第二轮全面审计。

独立临时文件位于：

- `C:/Users/50469/AppData/Local/Temp/test_specflow_cr07_astra_review.py`
- `C:/Users/50469/AppData/Local/Temp/run_specflow_cr07_astra_review.py`

仓库回归位于 `test_report_queries.py` 的事件元数据缺口、正式覆盖来源片段测试，以及
`test_review_cli.py` 的无效端口/地址零派发测试。最终全仓库门禁结果单独记录在
`CR02-TASK-07-completion.md`，不以审查通过替代运行证据。
