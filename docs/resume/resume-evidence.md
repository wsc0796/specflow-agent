# SpecFlow Agent — Resume Evidence

> 版本：2026-07-12 | 基于 M5 Product Vertical Slice

## 项目一句话

独立设计并实现了一个规范驱动的 AI 开发助手（Python/FastAPI），通过 Analyze → Generate → Review 三阶段 LLM Pipeline 对真实仓库进行只读分析，自动生成结构化技术规格和评测报告。

---

## STAR 子弹

### 子弹 1：架构设计

> **S** — LLM 直接生成代码缺乏可审查性和可回滚性，需要一套有边界的确定性 Pipeline。
> **T** — 设计一个从仓库证据收集到 AI 分析再到自动审查的完整工作流系统。
> **A** — 独立设计了 7 层模块化架构（Tool Framework → Evidence Pipeline → Context Builder → Token Budget → Worker State Machine → Artifact Delivery → Evaluation），使用 Python Protocol 定义抽象接口，所有模块通过显式公开 API 解耦。
> **R** — 交付 23 个渐进式任务、404 个测试、95%+ 覆盖率。系统可在 <30 秒内完成一个仓库的 Analyze → Generate → Review 完整链路，产出 10 个结构化产物。

**简历版（1 行）：** 独立设计并实现了一个 7 层模块化的 AI Pipeline 系统（Python/FastAPI），23 个渐进式任务、404 个测试，支持对任意 Python 仓库的只读分析和自动审查。

---

### 子弹 2：安全工程

> **S** — AI Agent 访问仓库文件存在路径穿越、凭据泄露、敏感文件读取等安全风险。
> **T** — 构建一套只读、可验证、有边界的仓库访问工具层。
> **A** — 实现了沙箱化的 RepositoryToolSet（list_files / search_code / read_file），包含 5 层安全防护：路径穿越拦截、符号链接边界检查、敏感文件名过滤、输出内容脱敏（正则匹配 sk-* / JWT / api_key）、文件大小和调用次数硬限制。在 1,954 字节 trace 输出和 10 个 Artifact 中均实现零凭据泄露。
> **R** — 安全扫描覆盖全量 Live Provider 运行产物，验证零 API Key、零 Token、零外部路径泄露，目标仓库零修改。

**简历版（1 行）：** 为 AI Agent 设计了 5 层安全防护的沙箱化仓库访问工具，通过真实 Provider 端到端验证零凭据泄露。

---

### 子弹 3：测试与质量工程

> **S** — AI 相关系统的不确定性使传统测试难以覆盖边界场景和失败路径。
> **T** — 建立一套支持 Mock 确定性验证 + 真实 Provider 合同检查的测试体系。
> **A** — 设计了 MockFirst 测试策略：MockLLMClient 替代真实 API 实现确定性回归；10 维度人工 Rubric（0/1/2 分制）分离自动检查与内容质量评估；实现了 Live Artifact 导入验证器（检查 artifact 完整性、hash lineage、Worker trace、只读工具调用、路径合法性、secret 模式）。CLI 测试从"接受任何非零退出码"收紧为"必须验证完整 10 文件产出和 manifest status==completed"。
> **R** — 404 个测试全通过。发现并修复了 CLI runner 只注册 analyze handler 导致 generate/review 永远失败的严重 Bug。Mock 合同评测 3 个案例全通过。

**简历版（1 行）：** 建立 MockFirst 确定性测试 + 10 维人工 Rubric 评估体系，404 测试全绿，发现并修复了 CLI Pipeline 的致命断链 Bug。

---

### 子弹 4：问题诊断与工程判断

> **S** — Live Provider 首次真实运行返回 exit code 4，表象是"失败"。
> **T** — 在不读取环境变量和 API Key 的前提下，仅通过 Artifact 审查定位根因。
> **A** — 通过逐层追溯 trace.json 的 fallback_level → analysis.json 的 degraded 标记 → review.json 的 REJECT 决策链，定位到根因是 CLI runner 使用最小 ProjectContext（空框架/ORM/数据库字段）而非完整 scanner 输出，导致 LLM 无法生成有效分析。判断这是 Pipeline 集成缺口而非 AI 质量问题，Review Worker 的诊断结果是正确的。
> **R** — 将退出码 4 从"失败"正确重分类为"degraded + 正确 REJECT"，写入 M5 收口记录的已知限制，排入 M6 scanner 集成计划。避免了对正常工作的代码进行无效排查。

**简历版（1 行）：** 通过 Artifact 链逆向诊断，将 Live 运行退出码 4 从误判的"失败"正确定性为 Pipeline 集成缺口，展现了独立排障能力。

---

## 技术关键词

`Python 3.12` `FastAPI` `SQLAlchemy` `Pydantic v2` `Jinja2` `pytest` `ruff` `Protocol` `State Machine` `Token Budget` `Mock LLM` `OpenAI-compatible API` `DeepSeek` `SQLite` `uv`

## 量化数据

| 指标 | 数值 |
|------|------|
| 总代码任务 | 23 个 (T-001 ~ T-023) |
| 测试数量 | 404 passed, 2 skipped |
| Python 源模块 | 30+ |
| 架构层数 | 7 层 |
| Worker Pipeline 延迟 | ~27s (Analyze 7.7s + Generate 9.4s + Review 10.4s) |
| Live 运行 Token 消耗 | ~4,077 (input 1,694 + output 2,383) |
| 安全防护层 | 5 层 |
| 评测维度 | 10 维 (0/1/2 分制) |
| 人工 Rubric 得分 | 13/20 (degraded 运行，pipeline 集成缺口) |
| Live 运行凭据泄露 | 0 |
