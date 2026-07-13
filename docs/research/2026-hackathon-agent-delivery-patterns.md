# 从黑客松评审反推：Agent 项目如何从 Demo 走向可交付服务

> 调研日期：2026-07-13。本文只采用赛事主办方、赞助方或平台公开的第一方规则/仓库；
> 它总结的是“可被外部评审验证的交付模式”，不是把黑客松原型等同于生产系统。

## 结论

对 Agent 项目，外部评审反复考察的不是 Agent 数量，而是下面这条证据链：

```text
明确业务角色与决策
→ 可交互的核心闭环
→ 可复现的代码、测试与说明
→ 可观察的演示和结果
→ 有边界的可持续演进计划
```

因此，SpecFlow 不应继续向“通用多 Agent 平台”扩张。它应选定一个窄而真实的研发
工作流，把现有受控运行时作为内核，交付一个能被开发团队实际调用、审阅和追踪的服务。

## 一手证据：近期赛事实际奖励什么

| 外部模式 | 第一方证据 | 对项目的含义 |
| --- | --- | --- |
| **Agent 项目既要可复现，也要有可量化价值** | [AWS AI Agent Global Hackathon（2025）官方规则](https://aws-agent-hackathon.devpost.com/rules) 将技术执行（含 well-architected、reproducible）设为 50%，可量化业务价值/影响为 20%，并要求工作 Agent 的部署、公开源码、架构图和真实运行的约 3 分钟视频。 | CI、测试和架构只能证明“能复现”；还必须针对一个业务流程定义可测的成功指标。 |
| **先验收可验证性，再比较方案** | [Databricks AI Agent Hackathon（2025）](https://databricks-hackathon.devpost.com/rules) 的第一阶段按 GitHub 链接可访问、演示视频时长、可访问的 demo/test build 做通过/不通过筛选；通过后才比较业务适用性、完整性与架构。 | README、代码、启动/测试步骤、可运行入口和演示不是“包装”，而是产品最低交付面。 |
| **业务问题优先于 Agent 炫技** | 同一 [Databricks 规则](https://databricks-hackathon.devpost.com/rules) 将 “Business Applicability” 定义为是否解决行业中的真实业务问题；[Microsoft RAG Hack](https://github.com/microsoft/RAG_Hack) 也把 impact、technical usability 和赛道契合列为评审维度。 | 先说明谁在什么节点需要它、要做什么决定、失败会带来什么成本；“用了六个 Agent”只能作为实现说明。 |
| **核心功能必须能被看到和操作** | [Hack for Impact NYC 2025 官方规则](https://hack-for-impact-nyc.devpost.com/rules) 要求可工作的 MVP，评审者能交互或观察核心功能；同时要求源码仓库及 README 的运行/测试说明，Demo 要展示问题、功能与创新点。 | 静态架构图和一次 CLI 输出不足够；应有一个从业务请求到结果被消费的完整路径。 |
| **架构质量是“可扩展且不推倒重来”** | [Databricks 规则](https://databricks-hackathon.devpost.com/rules) 明确询问应用是否能以线性成本扩展、能否不大幅重写而容纳新功能；[Hack for Impact NYC 2025](https://hack-for-impact-nyc.devpost.com/rules) 也以可维护/部署/增长考虑评价可持续性。 | 工程化不等于 Kubernetes。应先证明职责边界、状态恢复、版本/CI 事实源和可替换的适配层。 |
| **Demo 与文档本身属于执行质量** | [GitHub “For the Love of Code” 2025 官方规则](https://github.blog/wp-content/uploads/2025/07/ftloctcs.pdf) 将“功能完整、经过打磨、README 或 demo 清楚解释项目”列入 Execution & polish；[AWS × Impetus GenAI Hackathon 2025 官方要求](https://impetusawsgenaihackathon.devpost.com/updates/37074-quick-check-hackathon-submission-requirements) 要求部署链接、测试说明、架构图和展示实际运行环境的约 3 分钟视频。 | 一个陌生人必须能在五分钟内理解价值、跑通示例、知道结果是否可信和哪里不保证。 |
| **AI 的使用需要透明，而非冒充全自动** | [MLH 规则（HackTX 2025 页面转载的 MLH 标准）](https://hacktx2025.devpost.com/rules) 允许 AI 辅助开发，但要求披露所使用的 AI 工具；其基础评审也问“是否工作”。 | 对 live provider、mock benchmark、历史验证和未覆盖风险做诚实分层，反而提高可信度。 |

### 不应误读的地方

MLH 的通用黑客松规则明确说，不会因为代码不生产级而扣分。这说明黑客松“能演示”
不等于生产可用；但 Databricks、AWS 等面向企业 Agent 的赛事已经把可测试入口、
业务适用性、架构和部署说明变成评审对象。SpecFlow 的目标应取后者的交付纪律，
而不是为了竞赛去堆部署名词。

## 映射到 SpecFlow：已有资产与真正的缺口

以下是对当前仓库的本地观察，不是外部赛事声明。

| 交付维度 | 已有事实 | 仍缺什么，才不像框架 Demo |
| --- | --- | --- |
| 受控执行 | 固定六 Agent 拓扑、Schema Handoff、RuntimeGuard、只读 repository evidence、Artifact/Trace。 | 一个业务角色能主动发起、查询并使用结果的明确工作流。 |
| 运行交付 | mock-only Run API、SQLite 生命周期、被中断 Run 的恢复语义。 | 面向具体业务对象的请求契约和结果消费方式；不能把 mock-only 描述成生产异步平台。 |
| 可验证性 | 671 tests、CI、12-case mock benchmark、版本事实门禁。 | benchmark 目前证明确定性契约与回归，不证明代码审查“发现率”或业务收益。 |
| 演示 | 三分钟讲解、Demo 脚本、README 边界声明。 | 一条展示真实输入、用户决策和可追溯输出的端到端产品 Demo。 |

## 推荐的唯一业务切口：研发变更方案评审服务

不要把当前能力改名为“AI 自动代码审查”。它目前不读取 Git diff、也不应承诺自动
评论或合并 PR。更诚实、也更贴合已有能力的切口是：

> **研发负责人或开发者在改动开始前提交“变更需求 + 已登记的只读仓库”；SpecFlow
> 返回带证据引用的技术方案、风险清单和测试建议，供人工评审决策。**

它把现有输入/输出直接放进真实工作流：需求评审会前的准备，而不是虚构一个“全自动
开发 Agent”。

最小闭环应能用一句话描述：

```text
开发者提交变更需求 → 服务创建受控 Run → 负责人查看带 evidence/trace 的方案、风险和测试建议 → 人工接受、修改或拒绝
```

### 这个切口的工程化验收标准

1. **角色与决策固定**：明确开发者提交什么、负责人依据什么 Artifact 做批准/退回决定；不要泛称“用户”。
2. **请求可追踪**：每个 Run 关联 repository alias、需求摘要/哈希、policy 版本、状态、Artifact 引用和失败原因；不记录或泄露仓库外的敏感内容。
3. **结果可消费**：输出不是终端日志，而是一份结构化评审包：结论、证据、风险等级、待确认问题、测试建议、可复制链接/ID。
4. **失败有产品语义**：拒绝、预算耗尽、运行时失败和中断恢复必须对调用者可见；禁止静默把失败伪装成成功建议。
5. **五分钟可验证**：全新 clone 可按 README 跑测试；Demo 显示一次成功 Run、一次受控失败/恢复、一次 Artifact 查询；每一步都有预期结果。
6. **指标只报已测内容**：保留 12-case mock benchmark 作为契约稳定性证据；若要宣称“风险发现率/节省评审时间”，先建立带人工标注的真实变更任务集和基线，分别报告覆盖范围、失败数、时延、成本与误报。

## 建议的演进顺序（不是立即授权开发）

### A. 先完成产品叙事与可演示闭环

这一步主要是文档和演示收口，不需要增加 Agent、RAG、MCP 或动态拓扑：

- 将主页定位为“研发变更方案评审服务”，并明确是 human-in-the-loop；
- 用一个固定公开仓库和一个固定需求，演示创建 Run、轮询状态、读取 Artifact、人工决策；
- 为 Demo 附一页“可验证清单”：输入、预期 Artifact、CI run、已知限制；
- 把 Mock、历史 live 验证、真实质量评测分为三类证据，避免互相替代。

### B. 再做一个垂直业务切片

只有在 A 获得真实用户反馈后，再以独立任务契约实现：项目/仓库登记、受控 Run 的
异步执行语义，和“评审结论已被人工处理”的最小记录。此阶段的价值在于业务对象和
状态机完整，不在于引入 Redis、WebSocket、向量库或多租户。

### C. 最后才验证实际效果

收集一小组已关闭的公开 issue/变更需求，由人工先标注风险与测试要点；在不泄露私有
代码的前提下，比较人工基线与 SpecFlow 辅助的覆盖、误报、耗时和不可回答率。没有这
一步时，项目应只声称“受控、可复现、可审计”，不应声称“提升质量”或“节省成本”。

## 对下一次 Hackathon / Demo Day 的提交包

按上述一手规则反推，一套足够强的提交包应包含：

- 1 句用户/业务问题 + 1 个明确的非目标；
- 可访问的演示入口或测试 build，以及无凭据也能复现的 mock path；
- 公开仓库、开源许可、安装/测试/安全边界说明；
- 一张架构图，标出不可信 LLM 输出如何经 Schema、Guard、只读工具和 Artifact 约束；
- 3 分钟视频：问题（20 秒）→ 实际 Run（90 秒）→ Trace/失败语义（40 秒）→ 边界和下一步（30 秒）；
- 一页指标表：CI、测试、契约 benchmark 与真实评测分别列出，绝不合并成“准确率”。

这会把 SpecFlow 的竞争点从“我实现了六个 Agent”改为“我交付了一个可审计的研发评审
工作流，并能诚实说明它的验证范围和不适用范围”。

## 来源清单

1. [Databricks Hackathon: Build an AI agent, agent system, or agent application（Devpost 官方规则，2025）](https://databricks-hackathon.devpost.com/rules)
2. [AWS AI Agent Global Hackathon 官方规则（Devpost，2025）](https://aws-agent-hackathon.devpost.com/rules)
3. [Hack for Impact NYC 2025 官方规则（Devpost）](https://hack-for-impact-nyc.devpost.com/rules)
4. [HackTX 2025 / MLH Hackathon Rules（Devpost）](https://hacktx2025.devpost.com/rules)
5. [MLH Contest Terms（官方仓库，2025–2026）](https://github.com/MLH/mlh-policies/blob/main/contest-terms.md)
6. [Microsoft RAG Hack 官方仓库](https://github.com/microsoft/RAG_Hack)
7. [GitHub For the Love of Code Contest 官方规则（PDF，2025）](https://github.blog/wp-content/uploads/2025/07/ftloctcs.pdf)
8. [AWS × Impetus GenAI Hackathon 官方提交要求（Devpost，2025）](https://impetusawsgenaihackathon.devpost.com/updates/37074-quick-check-hackathon-submission-requirements)
9. [TiDB AgentX Hackathon 官方规则（Devpost，2025）](https://tidb-2025-hackathon.devpost.com/rules)
