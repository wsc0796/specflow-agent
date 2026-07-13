# SpecFlow Agent — 简历 V0（投递版）

> 当前可引用事实：v1.1.0 未发布候选，671 passed、2 skipped；12-case
> mock contract benchmark；CI quality / benchmark / security 门禁。最新已发布
> tag 仍为 v1.0.1。不要把本页的候选状态写成“已发布生产系统”。

## 主项目名称

**SpecFlow Agent｜面向代码仓库理解的受控多 Agent Workflow**

## 简历 Bullet（推荐两条）

- 设计并实现面向本地 Python 仓库的受控六 Agent 分析工作流：由确定性
  Coordinator 固定拓扑与执行阶段，结合只读 Repository Evidence Pipeline、
  Schema-validated Handoff 与 RuntimeGuard，约束 LLM 的输入、预算、返工与
  输出边界。
- 构建 12-case mock artifact-contract benchmark 与 CI 门禁，覆盖仓库理解、
  变更规划和风险审查；v1.1.0 候选通过 671 项自动化测试，并保留 Trace、
  Artifact 与安全失败语义作为可复查证据。

## 精简版（一条）

> 实现受控六 Agent 代码仓库分析系统，以确定性编排、只读证据采集、Schema
> Handoff 和 RuntimeGuard 降低 LLM 工作流不确定性；通过 12-case mock
> benchmark、671 项自动化测试和 CI 门禁提供可复现工程证据。

## 技术栈

Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy · pytest · Ruff · GitHub
Actions

## 证据与边界

- 可复验证据：固定六 Agent 拓扑、12-case mock benchmark、671 passed、
  artifact/trace/schema contracts、read-only repository access。
- 不要宣称：生产部署、真实用户流量、模型语义准确率、成本节省或 mock
  benchmark 的 live-model 质量。
- 历史 M6 曾在授权环境完成 DeepSeek live-provider 验证；这是单独的历史
  记录，不是 v1.1.0 当前候选的验证证据。除非面试官追问，不放进主 bullet。

## 面试追问时的证据入口

- 当前事实与限制：[current-resume-evidence.md](current-resume-evidence.md)
- 可复现 Demo：[portfolio-release-demo.md](../demo/portfolio-release-demo.md)
- 发布真相门禁：[T-059 completion report](../reports/T-059-completion-report.md)
