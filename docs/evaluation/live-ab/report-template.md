# M7 Live Provider A/B 分析报告

> 待 T-034 三个案例数据采集完成后填入。

## 实验环境

| 配置 | 值 |
|------|-----|
| Provider | DeepSeek API |
| Model | deepseek-v4-flash |
| Target repo | sky-takeout-python |
| SpecFlow commit | <填> |
| Target repo commit | <填> |
| Temperature | 0.0 |

---

## Case 1：订单超时自动取消

### 自动指标

| 维度 | Legacy | Multi-Agent | Delta |
|------|--------|-------------|-------|
| Exit code | <填> | <填> | |
| Wall time (ms) | <填> | <填> | |
| Input tokens | <填> | <填> | |
| Output tokens | <填> | <填> | |
| Total tokens | <填> | <填> | |
| LLM calls | 3 | 6 | +3 |
| Discovered files | <填> | <填> | |
| Fallback count | <填> | <填> | |
| Degraded count | <填> | <填> | |
| Schema validated | N/A | <填>/6 | |
| Revision count | N/A | <填> | |
| Review decision | <填> | <填> | |
| Parallel speedup | N/A | <填>x | |

### 人工评分 (1-5)

| 维度 | Legacy | Multi-Agent | 备注 |
|------|--------|-------------|------|
| 需求覆盖度 | <填> | <填> | |
| 文件引用准确率 | <填> | <填> | |
| 风险覆盖度 | <填> | <填> | |
| 测试完整度 | <填> | <填> | |
| 架构可执行性 | <填> | <填> | |
| 输出冗余度 | <填> | <填> | |
| 人工修改成本 | <填> | <填> | |

---

## Case 2：Redis 缓存失效

（同上表格式）

---

## Case 3：下单幂等控制

（同上表格式）

---

## 汇总

| 维度 | Legacy (avg) | Multi-Agent (avg) | Delta |
|------|-------------|-------------------|-------|
| Total tokens | | | |
| Wall time | | | |
| Fallback count | | | |
| 需求覆盖度 | | | |
| 风险覆盖度 | | | |
| 测试完整度 | | | |

---

## 结论

### 多 Agent 增益

<基于数据的结论>

### 多 Agent 代价

<Token 和延迟增量>

### 适用场景

```text
简单单模块需求 → Legacy（成本更低）
跨模块需求 → Multi-Agent（风险覆盖更全）
高风险需求（支付/事务/安全）→ Multi-Agent（必须多维度审查）
```

---

## 可写入简历的结论

<只保留有数据支撑、可直接引用的结论>
