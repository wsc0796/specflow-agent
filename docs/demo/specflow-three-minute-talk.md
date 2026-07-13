# SpecFlow Agent — 3 分钟项目讲解

> 面向后端 / AI Agent 实习面试。讲“可验证的工程取舍”，不要背模块清单。

## 0:00–0:25｜问题

“我做 SpecFlow 是想解决一个很具体的问题：给定一条需求和一个本地 Python
仓库，怎样让 LLM 先基于受限的仓库证据做分析、技术方案、测试策略和风险审查，
同时不让模型自己决定权限、拓扑或执行边界。”

## 0:25–1:05｜架构

“核心是固定六 Agent 拓扑。RepositoryAnalyst 先收集只读证据；Design、
TestStrategy、RiskReview 并行；然后 Synthesis 汇总，Review 收口。拓扑、
依赖和阶段由确定性 Coordinator 控制，LLM 只做受约束的语义工作。Legacy
Analyze→Generate→Review 管道保留为 A/B 基线。”

## 1:05–1:50｜我最关键的设计

“我重点解决的是 Agent 容易失控的问题。第一，仓库读取只允许 list、search、
read 等只读工具，拒绝路径穿越和敏感文件。第二，Agent 之间传递的是带 schema
和 canonical JSON hash 的结构化 handoff，不是自由文本接力。第三，RuntimeGuard
限制 token、调用、并发和 revision；模型不能临时增加 Agent 或无限返工。失败会
被归类并留下 artifact 与 trace，而不是伪装成成功。”

## 1:50–2:25｜如何证明它不是拼框架

“我没有把 benchmark 写成模型效果宣传，而是建立 12 个固定 mock case：4 个仓库
理解、4 个变更规划、4 个风险审查。它验证 artifact、schema、状态和安全边界能否
稳定复现。当前 v1.1.0 候选有 671 个自动化测试，并在 CI 中执行 quality、
benchmark 和 secret-scan 门禁。”

## 2:25–3:00｜边界与下一步

“它目前不是生产 Agent 平台：没有队列、鉴权、多实例、真实流量或 semantic
accuracy claim。Run API 也只支持 mock-only 单进程生命周期。历史上 M6 做过一次
授权的 DeepSeek live-provider 验证，但我不会把它混进当前候选的 benchmark 结论。
如果继续做，我会先从真实使用需求出发，而不是盲目加 RAG、MCP 或更多 Agent。”

## 讲完后可展示的三个页面

1. README 的 12-case benchmark 命令。
2. 一个 case 的 `manifest.json`、`handoffs.json`、`traces.json`。
3. `docs/resume/current-resume-evidence.md` 的证据与边界。
