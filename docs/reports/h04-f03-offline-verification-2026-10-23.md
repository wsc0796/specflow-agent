# H04 反馈送达与 F03 超时/503 诊断：离线修复结果

日期：2026-10-23。任务：[冻结范围与验收](../tasks/h04-f03-offline-verification-2026-10-23.md)。
基线：`859d34f80f816b91e21a5e075a33a234d074038d`。
分支：`codex/h04-f03-offline-verification`；验证对象为本报告同一交付中的代码补丁。

2026-10-24审查补记：本页数字保留7fd7f2f时的历史结果。独立审查指出当时测试替换了客户端工厂、没有覆盖实际attempt_executor；HTTPX的INFO日志也会记录配置端点。后续已把测试接回真实工厂/执行通道，并将安全结论限定到自有诊断及原生产物；见[审查收尾报告](./offline-review-closeout-2026-10-24.md)。不得据本页历史记录推导所有第三方日志都隐藏配置URL。

**H04 的具体反馈已到达三个可返工角色的实际模型请求；F03 的超时/503 原因已保留到原生 manifest/traces。全程离线，新增真实模型调用 0 次。**

## 复现与最小修复

### H04：发生返工，但反馈没有进入请求

旧流程给 RevisionTask 填入通用 finding，又只将它放入 context。
后续 `_validated_inputs` 未声明或投影该信息，Adapter 优先使用 validated_input，
导致实际返工消息没有 Review 的 summary/findings。

新增完整工作流测试使用真实 Provider 请求组装与 MockTransport：
Review 的特定标记只出现在其反馈中，捕获返工角色实际 HTTP 请求，
旧实现上 6 个角色/反馈形态组合均找不到该标记。

最小修复：

- `schema/models.py`：为 Design、TestStrategy、RiskReview 的输入增加可选的
  `RevisionFeedback`，包含目标、轮次、summary、findings，嵌套字段仍禁止额外键。
- `runner_multi.py`：在已有 Review 交接校验之后，从同一份已校验产物提取反馈；
  验证 REJECT、Review 目标、revision_task 目标和当前接收者相符；返工记录保留实际 finding。
- `agents/adapter.py`：新增独立 Revision Feedback 段完整序列化；从普通前序输出摘要中排除，
  避免经过 500 字符截断。首轮 `None` 不产生反馈段，原 Requirement 与业务输出合同保留。

未改变其他前序产物的截断策略、固定拓扑、允许返工角色或最多一轮的策略。
具体反馈是用于修订的评审数据，不增加工具或权限。

### F03：精确传输错误被最终失败产物丢失

旧 Provider 已把 ReadTimeout/503 映射为精确错误码，但没有附安全诊断对象；
Runner 的诊断白名单也不包含这两类。Adapter 虽保留错误码，最终 manifest 仍退化成
`MULTI_AGENT_RUN_FAILED`。

最小修复：

- `llm/diagnostics.py`：允许 `provider_transport` 阶段。
- `llm/providers/openai_compatible.py`：Timeout 和已映射为服务器错误的 5xx
  附该阶段的空事实诊断，不解析或复制错误正文。
- `runner_multi.py`：将 `PROVIDER_TIMEOUT`、`PROVIDER_SERVER_ERROR` 加入现有白名单。
  Adapter 原有 typed 诊断传递直接复用，无需为 F03 修改其错误处理。

失败产物现在保留错误码、角色、阶段索引及 `provider_transport`；
finish_reason/content_empty 未知，usage 为 null/unknown，schema_validation 为 not_run。
没有将未知费用/用量补为零，没有新增生产重试或恢复策略。

## 验证记录

| 检查 | 结果与含义 |
|---|---|
| H04 新回归在旧实现上 | 10 failed / 5 passed；6 个完整请求用例缺反馈，3 个可选输入正例不被接受，1 个目标错配未拒绝 |
| F03 新回归在旧实现上 | 4 failed / 6 passed；2 个 Runner 用例根因丢失，2 个 Adapter 持续失败缺诊断；成功路径原本通过 |
| H04 修复后聚焦组 | 127 passed；包含新增15例和既有交接、返工、Adapter相关回归 |
| F03 修复后聚焦组 | 149 passed；包含新增10例和既有Provider/诊断/弹性/Adapter回归 |
| 全量离线 pytest | 1094 passed、3 skipped、3 warnings，27.05秒 |
| Ruff check | 通过；仍有既有 test_coordinator.py 的 noqa 提示 |
| Ruff format --check | 222 files already formatted |
| git diff --check | 通过 |
| 真实模型调用 | 0；HTTP仅经MockTransport，保留全局真实HTTP阻断 |

两个聚焦组有重叠，不能相加为独立用例数量。新增测试总计25例：

- H04：三个角色 × 空/非空 findings 共6个请求级用例；长尾反馈超过500字符仍完整。
  三个输入正例、四种非法字段、非返工角色拒绝、目标错配拒绝，合计15例。
- F03：两种故障的完整工作流失败产物2例；两种故障 × 持续失败/立即成功/
  失败一次后成功/失败两次后成功，共8个Adapter机制用例，合计10例。

H04的Mock Review固定返回第二轮PASS，仅用来走通该控制分支；不证明模型真实纠错。
已有持续REJECT回归仍检查Review两次、返工一次、诚实保留拒绝终态。
F03产品路径仍是零重试：每个完整工作流fixture为六次planning加一次失败角色调用。
显式 `max_retries=2` 只用于Adapter机制测试，最多三次尝试，不能写为产品默认恢复能力。
失败尝试次数由测试记录；没有新增生产级逐尝试账本。

三项跳过均为既有Windows符号链接权限分支；未新增skip/xfail。
三项警告为两个既有Test类收集警告及既有TestClient依赖弃用警告。

## 验证环境与重放方法

独立工作区使用原工作区已有虚拟环境，不安装依赖。
通过PYTHONPATH与启动器检查确认导入来自新工作区；uv使用--no-sync。
测试进程内移除四个继承配置名：SPECFLOW_LLM_API_KEY、SPECFLOW_LLM_BASE_URL、
SPECFLOW_LLM_MODEL、SPECFLOW_LLM_TIMEOUT_SECONDS；不读取/打印其值，不修改用户环境。
测试所需配置由fixture显式设置，conftest的HTTPTransport阻断保持启用。

在已准备依赖的工作区可按同一口径运行：

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
uv run --no-sync python -B -c "import os, pytest; [os.environ.pop(k, None) for k in ('SPECFLOW_LLM_API_KEY','SPECFLOW_LLM_BASE_URL','SPECFLOW_LLM_MODEL','SPECFLOW_LLM_TIMEOUT_SECONDS')]; raise SystemExit(pytest.main(['-v','-p','no:cacheprovider']))"
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
```

原始本地记录目录：`D:\Documents\spec agent\outputs\h04-f03-offline-20261023`。
保留 h04-red.log、f03-red.log、h04-green-focused.log、f03-green.log、pytest-full.log、
ruff-check.log、ruff-format.log 和实际运行入口 run_offline_checks.py。

## 审查与范围检查

- H04独立只读审查检查来源绑定、首轮/其他角色隔离、空findings兼容、长反馈、Schema和返工轮数，未发现阻碍交付的问题。
- 主代理审阅F03差异与测试：不接收原始异常文本、不把未知usage填零，真实失败不被当成功。
- 同类位置检查限定为三个可返工角色、共用消息构建、两类传输映射、Runner白名单；都由本次回归覆盖。
- 网络连接错误、429、认证错误、其他诊断阶段及planning统一账本未扩入本任务。
- 只在独立工作区修改；原取证实验工作区及目标业务仓库未被本任务改动。

## 评测结论与简历边界

- H04a（反馈送达、隔离及结构合同）：离线验证通过。
- H04b（真实模型采用反馈、修复率、最终方案质量）：未运行，继续待补。
- F03a（ReadTimeout/503的默认产品失败传播、精确原生产物）：离线验证通过。
- F03b（Adapter显式重试边界及成功对照）：离线验证通过；未启用产品自动恢复。
- 仍未验证真实供应商故障恢复、生产级全链路逐尝试账本或普遍质量/成本收益。

技术成果与候选措辞见[本次简历证据](../resume/h04-f03-verified-claims-2026-10-23.md)。
用户选择并授权了问题、离线复现和最小修复；代码、测试与文档由Codex协作完成，
不自动登记为用户独立设计、编码或掌握。学习状态、Holdout与长期目标验收保持原口径。
