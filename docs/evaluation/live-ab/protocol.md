# M7 Live Provider A/B 实验协议

## 实验目标

在相同仓库、相同需求、相同 Provider 条件下，对比 Legacy 线性管道和 Multi-Agent 编排管道的输出质量、Token 成本和执行时间。

## 公平实验约束

- 同一个目标仓库
- 同一个 Git commit
- 同一个 Requirement
- 同一个 Provider + Model
- 相同 temperature (0.0) + max_tokens
- 相同 API 配置
- 独立输出目录
- 运行期间目标仓库只读

## 环境准备

```powershell
$env:SPECFLOW_LLM_BASE_URL = "https://api.deepseek.com"
$env:SPECFLOW_LLM_API_KEY = "<your-key>"
$env:SPECFLOW_LLM_MODEL = "deepseek-v4-flash"

# 记录环境信息
git -C "D:\Documents\暑假计划\specflow-agent" log --oneline -1
git -C "C:\Users\50469\github-projects\sky-takeout-python" log --oneline -1
```

## 三个案例

### Case 1：局部业务需求 — 订单超时取消

```text
需求：为订单增加超时自动取消功能
特点：业务流程、状态流转、定时任务、支付集成
```

```powershell
# Legacy
uv run specflow run --provider openai-compatible --model deepseek-v4-flash --repo "C:\Users\50469\github-projects\sky-takeout-python" --requirement "为订单增加超时自动取消功能" --output ".\evaluation-data\case-001\legacy"

# Multi-Agent
uv run specflow run --mode multi-agent --provider openai-compatible --model deepseek-v4-flash --repo "C:\Users\50469\github-projects\sky-takeout-python" --requirement "为订单增加超时自动取消功能" --output ".\evaluation-data\case-001\multi"
```

### Case 2：缓存一致性需求 — Redis 缓存失效

```text
需求：为菜品和分类查询增加 Redis 缓存，并处理更新后的缓存失效
特点：缓存一致性、缓存穿透、失效策略、并发写入
```

```powershell
# Legacy
uv run specflow run --provider openai-compatible --model deepseek-v4-flash --repo "C:\Users\50469\github-projects\sky-takeout-python" --requirement "为菜品和分类查询增加 Redis 缓存，并处理更新后的缓存失效" --output ".\evaluation-data\case-002\legacy"

# Multi-Agent
uv run specflow run --mode multi-agent --provider openai-compatible --model deepseek-v4-flash --repo "C:\Users\50469\github-projects\sky-takeout-python" --requirement "为菜品和分类查询增加 Redis 缓存，并处理更新后的缓存失效" --output ".\evaluation-data\case-002\multi"
```

### Case 3：并发幂等需求 — 防重复下单

```text
需求：为用户下单增加幂等控制，避免重复提交生成重复订单
特点：事务、并发、唯一约束、分布式锁、异常恢复
```

```powershell
# Legacy
uv run specflow run --provider openai-compatible --model deepseek-v4-flash --repo "C:\Users\50469\github-projects\sky-takeout-python" --requirement "为用户下单增加幂等控制，避免重复提交生成重复订单" --output ".\evaluation-data\case-003\legacy"

# Multi-Agent
uv run specflow run --mode multi-agent --provider openai-compatible --model deepseek-v4-flash --repo "C:\Users\50469\github-projects\sky-takeout-python" --requirement "为用户下单增加幂等控制，避免重复提交生成重复订单" --output ".\evaluation-data\case-003\multi"
```

## 数据记录

每次运行后记录：

```text
- 运行时间
- Exit code
- 总耗时（wall clock）
- 成功/失败的 Agent 数
- Token 总量（从 metrics.json 或 manifest.json）
- 发现的文件数（从 sources.json）
- Review decision
- Fallback/degraded 计数
```

## 注意事项

- 6 次 API 调用，每次约 30-60 秒，总计约 3-6 分钟
- 如果 Legacy 遇到 M5 已知的 Worker 失败，记录并跳过，不阻塞实验
- 所有运行数据保留在 `evaluation-data/` 目录
