# Live Case 001 — Run 级 Token 预算配置

状态:**DRAFT(Phase 4A 准备完成;运行前需 Phase 4B 用户批准)**

本案例用于首次真实 provider 运行(Phase 4B),随后由独立窗口执行 Phase 4C artifact 审计。

任务文本:

> 为 SpecFlow 增加 Run 级 Token 预算配置,涉及配置 Schema、RuntimeGuard、manifest、API、CLI、测试和文档。

关键文件:

- `request.json` — 任务请求与验收标准草案
- `frozen-config.json` — 冻结配置草案(全部 PENDING_USER_APPROVAL)
- `metadata.json` — 案例元数据
- `evidence-index.json` — 证据索引模板(运行后填充)
- `rerun.md` — 可复现步骤模板

边界:

- 不改变默认预算值(DECISION_D1 未决前)。
- 不调用任何真实模型,直到用户批准 API key、模型、最大费用、最大 token、最大 wall-clock。
- 不声称 production-ready 或质量提升。
