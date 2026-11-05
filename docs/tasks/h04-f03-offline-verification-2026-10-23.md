# H04 反馈送达与 F03 传输故障诊断：限定离线修复

日期：2026-10-23。用户已明确要求先用离线测试复现，再做最小修复，更新评测矩阵与可支撑的简历表述。
基线：859d34f80f816b91e21a5e075a33a234d074038d。
隔离工作区：C:\Users\50469\specflow-h04-f03-20261023。
分支：codex/h04-f03-offline-verification。

## 范围

- H04：将已校验 Review 的具体反馈，经声明的输入合同送到被选定返工角色的真实 LLMRequest；保留需求与既有输入；不让反馈被通用前序摘要截断吞掉。
- F03：ReadTimeout 与 HTTP 503 的有限诊断字段从 Provider 经 Adapter 到 Runner 的 manifest/traces；保持失败即停止和未知 usage 语义。
- 新增或扩展离线回归：真实请求组装、MockTransport 或 RecordingProvider；有效输出正对照、失败传播和敏感内容隔离。
- 更新完成报告、能力证据与工作区评测矩阵。

## 不改变

不运行真实模型，不读取 Holdout，不修改目标业务仓库，不改变模型配置、返工轮数、生产重试策略、并发拓扑或工具权限，不接入新框架/依赖，不推进学习模式。
H04 证明送达机制；离线替身按反馈返回内容不能证明真实模型纠错收益。
F03 证明指定传输故障的诊断传播；不声称自动恢复、所有故障覆盖或统一成本账本。

## 预计文件边界

H04：src/specflow/schema/models.py、src/specflow/runner_multi.py 的返工与输入投影、src/specflow/agents/adapter.py 的消息构建，以及相应离线测试。必要时仅触及直接相关的交接/返工类型。
F03：src/specflow/llm/diagnostics.py、src/specflow/llm/providers/openai_compatible.py、runner_multi.py 的故障白名单及对应测试；若有必要，只调整 Adapter 的诊断传递。
文档：本任务、docs/reports/ 下完成报告、docs/resume/ 下本次范围限定证据、外部评测矩阵。

## 验收

1. 保存红测：H04 的具体 finding 仅存在于 Review，原代码的实际返工消息缺失；F03 的原生失败产物丢失精确根因。
2. H04：具体反馈完整到达声明的返工目标，长反馈不受通用500字符摘要裁切；普通首轮不出现反馈；不绕过Schema、输入隔离或原需求；持续REJECT仍最多一轮。
3. F03：默认产品零重试下，超时/503在对应调用失败后停止；manifest/traces含精确错误码、角色、阶段，schema未运行，未知用量为null；不保留原始错误正文、认证内容或URL等不必要数据。
4. Adapter显式重试的测试只证明该机制，最多max_retries+1次；不得暗改产品默认配置。成功正对照能够继续通过校验边界。
5. 聚焦回归与全量离线pytest、Ruff check、Ruff format --check通过，保留所有失败记录。测试进程隔离继承的供应商配置，不读取或输出秘密值；保留既有HTTP阻断。
6. 文档区分已验证机制、待真实模型验证的效果、本人贡献；更新矩阵时保留历史证据版本。

## 交付

完成后按仓库约定做聚焦提交与审查分支推送，保留草稿审查，不合并。工作区评测矩阵同步更新，原始实验记录不改写。
