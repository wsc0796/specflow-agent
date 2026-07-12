# SpecFlow Agent — Demo 脚本

> 目标时长：3-5 分钟。可在终端直接演示，也可录屏。

## 准备

```powershell
# 确认环境
uv run pytest -q | tail -1        # 应输出: 607 passed
git log --oneline -1              # 确认最新提交

# 设置 API（演示时手动输入，不录 Key）
$env:SPECFLOW_LLM_BASE_URL = "https://api.deepseek.com"
$env:SPECFLOW_LLM_API_KEY = "<your-key>"
$env:SPECFLOW_LLM_MODEL = "deepseek-v4-flash"
```

## 时间线

### 00:00-00:20 项目介绍

```text
"SpecFlow 是一个可控多 Agent 代码分析系统。
给定一个代码仓库和一条需求，6 个专职 Agent 协作分析，
产出方案、测试策略、风险清单和 Review 结果。

不依赖 LangGraph——Coordinator、状态机、并行调度、
Handoff 校验全部自己实现。"
```

展示：
- 项目结构：`src/specflow/` 下的 agents/、coordinator/、plan/、handoff/ 模块
- 测试数：`uv run pytest -q | tail -1`

### 00:20-00:50 架构图

```text
                    Coordinator
                         │
                   ┌─────┴─────┐
                   ▼           ▼
           --mode legacy   --mode multi-agent
                   │           │
                   ▼           ▼
           AgentExecutor   Coordinator
           Analyze         ├── DeterministicPlanner
           Generate        ├── PlanCompiler
           Review          ├── SemanticPlanEnricher
                           ├── PlanValidator
                           ├── MultiAgentScheduler
                           └── RevisionController
```

口头解释：

```text
"两种模式：Legacy 是 Analyze→Generate→Review 串行，
 Multi-Agent 是 Coordinator + 6 Agent 4 阶段拓扑。

 最关键的架构决策是 M6-ADR-001：
 规则层拥有执行权，LLM 只补充语义描述。
 LLM 不能增加 Agent、不能改变依赖、不能提高返工轮数。"
```

### 00:50-01:30 执行 Multi-Agent Run

```powershell
uv run specflow run --mode multi-agent --provider openai-compatible --model deepseek-v4-flash --repo "C:\Users\50469\github-projects\sky-takeout-python" --requirement "为订单增加超时自动取消功能" --output ".\demo-output"
```

等待执行时解释：

```text
"6 个 Agent 分 4 个阶段执行：
 Stage 0：RepositoryAnalyst 扫描仓库，采集证据
 Stage 1：Design、TestStrategy、RiskReview 并行分析
 Stage 2：Synthesis 合并三个 Specialist 的结果
 Stage 3：Review 做最终 PASS/REJECT"
```

### 01:30-02:00 查看结果

```powershell
ls .\demo-output\run-multi-*
```

展示输出文件：

```text
"每次运行产出 6 个文件：
 manifest.json    — 运行元数据和全链路 Hash
 agent-outputs.json — 6 个 Agent 的原始输出
 handoffs.json    — 7 条结构化 Agent 间交接
 traces.json      — Agent 级 Trace（stage timing + parent span）
 sources.json     — 仓库证据采集结果
 metrics.json     — 统一指标（Token、延迟、并行加速比）"
```

### 02:00-02:40 展示 Agent 输出

```powershell
cat .\demo-output\run-multi-*\agent-outputs.json | python -m json.tool | head -40
```

展示关键字段：

```text
"每个 Agent 输出包含：
 agent_id、role、success、output、
 schema_validated（Pydantic 校验状态）、
 usage（Token 使用量）"
```

### 02:40-03:10 展示 Handoff 和 Trace

```powershell
cat .\demo-output\run-multi-*\handoffs.json | python -m json.tool
```

```text
"7 条 Handoff：
 repo-analyst → design/test/risk（并行阶段）
 design/test/risk → synthesis
 synthesis → review

 每条 Handoff 带 source_output_schema_id / target_input_schema_id，
 创建端和校验端用统一的 canonical_json_bytes() 做 Hash 验证。"
```

### 03:10-03:40 A/B 对比

展示 `docs/evaluations/M6-ab-comparison.md`：

```text
"同仓库、同需求，Legacy vs Multi-Agent：
 Legacy：3 worker 串行，10 个 artifact
 Multi-Agent：6 agent 4 阶段，Stage 2 并行，
              7 条显式 Handoff，6 个 AgentTraceSpan"
```

### 03:40-04:00 总结

```text
"SpecFlow 的核心价值：
 1. 不依赖第三方 Agent 框架，全部自建
 2. 确定性架构——规则层控制执行，LLM 只补充语义
 3. Agent 间契约可审计——Schema + Hash + Trace 三层防护
 4. 607 测试 + 真实 Provider 验证 + A/B 评测数据"
```

## 录屏备选：预录制模式

如果不想实时等待 API 调用，使用已准备好的 Artifact 目录：

```powershell
# 展示已有的一次成功运行
ls .\artifacts-live-multi\run-multi-e5b97497dfd5\
```

这样可以立即展示 6 个文件的内容，跳过等待时间。

## Demo Checklist

- [ ] `uv run pytest -q` 全绿
- [ ] 项目结构截图
- [ ] Multi-Agent 命令执行
- [ ] agent-outputs.json 内容
- [ ] handoffs.json 结构
- [ ] metrics.json 指标
- [ ] A/B 对比表
- [ ] 结束总结
