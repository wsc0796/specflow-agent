# Day 11 Multi-Agent Dev Report

- 日期：2026-09-22。
- 状态：`DAY11 COMPLETED / DAY12 READY`。
- 正式运行：唯一一次授权的 DeepSeek `deepseek-flash` Multi-Agent 20 Dev。
- 运行时间：2026-09-22T15:42:23+08:00 至 2026-09-22T16:09:53+08:00。
- 原始根目录：`data/day11/multi-agent-dev/`。
- 语义复核：`docs/study/evidence/day-11-multi-agent-semantic-review.json`。
- 学习者预测：`docs/study/evidence/day-11-pre-run-prediction.md`。

Day 11 完成表示“冻结身份下的一次正式运行、机械核对和语义复核已经形成”，不表示产品质量通过。
本次 20 个产品运行全部失败；该结果必须原样进入 Day 12，禁止重跑或筛掉失败样本。

## 1. Run Identity

| 字段 | 冻结值 |
| --- | --- |
| SpecFlow code revision | `bc75a6de3cef8bcbf3b0cbbddda00918003cfb0e` |
| Dataset / annotation | `v1` / `v1` |
| Dataset freeze | `bf77d19455cb989984dc4f909e6e7ca4b4f91aaf` |
| 目标仓库 / Gold revision | `08e5a66f8ea8216433c72744adab92aa07d99c45` |
| Provider / model | OpenAI-compatible / `deepseek-flash` |
| 输入投影 | `requirement` only |
| Source profile | `authorized-source-v1` |
| 公平性实验 | `controlled-cap-at-5` |
| 产品默认 max_selected_files | 10 |
| Benchmark effective max_selected_files | 5 |
| Evidence chars / tool calls | 80000 / 20 |
| Agent call guard / enrichment calls | 10 / 6（enrichment 不计入 guard） |
| Revision / Agent retry / Provider retry | 1 / 0 / 0 |
| Provider timeout | 60 秒 |

运行前检查确认：HEAD 与冻结 revision 一致；runtime source clean；20 个唯一 Dev ID 与冻结 manifest
一致；输出目录没有 attempts/inputs；Holdout metadata 仍为 execution_count=0、results_available=false。
未读取或运行 Holdout 内容。

## 2. Pre-run Learner Prediction

学习者原始预测已在 Provider 调用前保存：

```text
1.Repository Analyst  ，不清楚
2.Repository Evidence  &#x20;
3.业务结果校验层
```

- Receiver 预测：`Repository Analyst`。
- 理由：学习者明确写为“不清楚”，保持 incomplete，不由 AI 代填。
- 运行后实际 receiver：`repository-analyst-agent-v1`；receiver 预测一致。
- Q2 的“Collector matched Gold”前提无法从本次 D001 artifacts 证明，因此不事后改写预测。
- Q3 的“Gold 已进入 LLMRequest”前提在 D001 实际不成立；本次不能把“业务结果校验层”判成已验证。

## 3. 20-case Execution Completeness

| 项目 | 数值 |
| --- | ---: |
| Planned / attempted / not started | 20 / 20 / 0 |
| Unique case / attempt / run_id | 20 / 20 / 20 |
| Returned / execution_error / interrupted | 20 / 0 / 0 |
| Top-level timeout / duplicate / rerun | 0 / 0 / 0 |
| Exit code 3 | 20 |
| Product completed / failed | 0 / 20 |
| `EVIDENCE_NOT_FOUND` | 4 |
| `MULTI_AGENT_RUN_FAILED` | 16 |
| Attempt/artifact directories | 20 / 20 |
| `_COMPLETE` / integrity files | 20 / 20 |

| Case | Attempt ID | Exit | Product state | Failure | Request records | Task success |
| --- | --- | ---: | --- | --- | ---: | --- |
| SF-RT-D001 | `SF-RT-D001-0c271ff0f524` | 3 | failed | `MULTI_AGENT_RUN_FAILED` | 7 | fail |
| SF-RT-D002 | `SF-RT-D002-00a5b1b59e56` | 3 | failed | `MULTI_AGENT_RUN_FAILED` | 7 | fail |
| SF-RT-D003 | `SF-RT-D003-499de7034b5e` | 3 | failed | `MULTI_AGENT_RUN_FAILED` | 7 | fail |
| SF-RT-D004 | `SF-RT-D004-e42051f56f7e` | 3 | failed | `MULTI_AGENT_RUN_FAILED` | 7 | fail |
| SF-RT-D005 | `SF-RT-D005-73adaf54d4fc` | 3 | failed | `MULTI_AGENT_RUN_FAILED` | 7 | fail |
| SF-RT-D006 | `SF-RT-D006-dd718df09e94` | 3 | failed | `EVIDENCE_NOT_FOUND` | 0 | fail |
| SF-RT-D007 | `SF-RT-D007-b1cb47fa6f53` | 3 | failed | `EVIDENCE_NOT_FOUND` | 0 | fail |
| SF-RT-D008 | `SF-RT-D008-71c58061b6e5` | 3 | failed | `MULTI_AGENT_RUN_FAILED` | 7 | fail |
| SF-RT-D009 | `SF-RT-D009-bb520b4d3fe6` | 3 | failed | `EVIDENCE_NOT_FOUND` | 0 | fail |
| SF-RT-D010 | `SF-RT-D010-12cae7daa377` | 3 | failed | `EVIDENCE_NOT_FOUND` | 0 | fail |
| SF-RT-D011 | `SF-RT-D011-1526be61440a` | 3 | failed | `MULTI_AGENT_RUN_FAILED` | 7 | fail |
| SF-RT-D012 | `SF-RT-D012-d231ef9d6469` | 3 | failed | `MULTI_AGENT_RUN_FAILED` | 7 | fail |
| SF-RT-D013 | `SF-RT-D013-430d06f9ccac` | 3 | failed | `MULTI_AGENT_RUN_FAILED` | 7 | fail |
| SF-RT-D014 | `SF-RT-D014-669f109e0060` | 3 | failed | `MULTI_AGENT_RUN_FAILED` | 7 | fail |
| SF-RT-D015 | `SF-RT-D015-c6487c64698e` | 3 | failed | `MULTI_AGENT_RUN_FAILED` | 7 | fail |
| SF-RT-D016 | `SF-RT-D016-fdaa0942d59a` | 3 | failed | `MULTI_AGENT_RUN_FAILED` | 7 | fail |
| SF-RT-D017 | `SF-RT-D017-f810c9f06188` | 3 | failed | `MULTI_AGENT_RUN_FAILED` | 7 | fail |
| SF-RT-D018 | `SF-RT-D018-1d0d401996ca` | 3 | failed | `MULTI_AGENT_RUN_FAILED` | 7 | fail |
| SF-RT-D019 | `SF-RT-D019-5840809e6719` | 3 | failed | `MULTI_AGENT_RUN_FAILED` | 7 | fail |
| SF-RT-D020 | `SF-RT-D020-e131f3b86055` | 3 | failed | `MULTI_AGENT_RUN_FAILED` | 7 | fail |

## 4. Task Quality

冻结 expected_properties/forbidden_claims 的 AI 复核结果：

- task_success：0 pass / 20 fail / 0 unknown / 0 N/A。
- 判定理由：20 个 case 均没有最终任务答案；4 个在 Evidence 边界停止，16 个在 Repository Analyst
  request 观察后、任何 Agent stage 完成前失败。缺少必要输出属性，因此不是 Schema/结构成功。
- contract_run_success：20 unknown。现有冻结 profile 只适用于旧 Mock portfolio，不能冒充 Live
  Dataset v1 profile。
- artifact observation：20 fail。所有运行都有受限失败 manifest、完整性文件和 `_COMPLETE`，但没有
  完整成功 artifact set。
- citation_support：unknown；没有最终 claims/citations，也没有冻结 claim↔citation scorer。
- safe_abstention：unknown；失败终态不能自动算正确拒答，且没有最终响应可检查语义。
- source_reference_validity：unknown；没有 case 产出 `sources.json` 或最终引用。

## 5. Evidence Path — matched → selected → projected → request

| 观察面 | 本次事实 |
| --- | --- |
| discovered | 每次读取固定源码快照；失败 manifest 记录 203 discovered files |
| matched / selected / extracted | 16 个通用失败未持久化 `sources.json`，完整计数 unknown |
| zero excerpts | D006、D007、D009、D010 明确 `EVIDENCE_NOT_FOUND`，selected/excerpt=0 |
| projected | 16 个 Repository Analyst 请求包含通用 Repository Evidence；4 个零调用 |
| requested | 112 条 request-boundary 记录：96 enrichment + 16 Repository Analyst |
| downstream receivers | Design/Test/Risk/Synthesis/Review 均为 0，因为 Stage 0 未完成 |
| Gold fact coverage | 14 个 eligible case、23 个 Gold facts；完整支持 0/23 |

五个 request 中出现了 Gold locator 的路径候选，但逐项核对均缺少至少一个必要源码片段或条件；不能把
“出现同路径”升级为事实覆盖。输入隔离检查为 pass：20 个 payload 均只有公共 7 字段；payload/request
中的 Gold、expected_properties、forbidden_claims、study path 标记均为 0。

## 6. Risk / No-evidence Behavior

D006、D007、D009、D010 在零 excerpt 时按 T-072 fail closed：每项 observation-status 明确为
0 次 LLM request，且保存 `EVIDENCE_NOT_FOUND`、manifest、artifact-integrity 和 `_COMPLETE`。
这证明无 Evidence 路径没有继续进入 Coordinator/Agent；它不证明固定仓库里真的不存在答案，可能仍是
keyword/ranking/selection 漏检。

其余 16 个 case 的失败发生在 Repository Analyst request 观察之后、validated Stage 0 result 之前。
由于失败 artifact 不保存 Provider response/error、未提交的 Stage 0 result，worker stderr 又只被父进程
捕获而未写 journal，现有证据无法区分 Provider、JSON、输出 Schema 或 stage validation 根因。

## 7. Latency / Calls / Observed Token Usage

| 指标 | 值 |
| --- | ---: |
| All-attempted total latency | 1,649,304.614 ms |
| Mean | 82,465.231 ms |
| P50 | 92,801.186 ms |
| P95 | 122,133.696 ms |
| Min / max | 3,207.965 / 131,638.483 ms |
| Request-boundary records | 112 |
| Coordinator enrichment / Repository Analyst | 96 / 16 |
| Confirmed zero-call runs | 4 |
| Provider/top-level retries | 0 / 0 |
| Completed revisions | 0 |

Token completeness：4/20 个零调用 run 完整，16/20 的 response usage 不可得；run-level coverage=0.2。
112 是 request-observer 边界记录，不证明 HTTP delivery、Provider 完成或计费次数。完整 Token 总量为
unknown，Day 10/Day 11 成本比较为 not_comparable；不能把 observed subtotal 0 写成全量成本 0。

## 8. Measurement Gaps

1. 16 个通用失败没有持久化 Provider response/error 或 worker stderr，根因只能定位到
   “Repository Analyst request 后、validated Stage 0 result 前”。
2. 失败路径没有 `sources.json`，所以 matched/selected/extracted 的 Gold 级最早缺口不能确定。
3. Response usage、Coordinator enrichment usage 均未形成完整 ledger；HTTP delivery 也为 unknown。

这些缺口只限制归因和成本结论，不抹去 20 次 attempted、产品终态和 request observation 事实。

## 9. D001 Prediction vs Actual

| 检查点 | 结果 |
| --- | --- |
| Learner predicted receiver | Repository Analyst |
| Actual receiver | `repository-analyst-agent-v1`；一致 |
| Gold | `src/specflow/evidence/collector.py` / `EvidenceCollector._rank_files` |
| matched / selected / extracted | unknown；失败路径没有 `sources.json` |
| generic evidence projected | yes |
| Gold fact projected / LLMRequest | no / no |
| final answer used/cited | N/A；无完成 Agent output 或最终答案 |

D001 的实际请求有通用 Repository Evidence，但不含 Gold path、`_rank_files` 实现、`sort_key` 或完整
priority/match_count/tie 条件。Gold 最早缺口无法在 retrieval-match、ranking-selection、
read-extraction、context-projection 之间唯一定位；只能确认 Gold 没有进入 request。产品随后又在该
Repository Analyst request 观察后、Stage 0 result 形成前失败，generation 与 validation 仍不可区分。

因此：receiver 预测与实际一致；Q2 的 matched 前提未被证明；Q3 的“Evidence 已进入 request”对通用
Evidence 成立、对 Gold 不成立，不能用本次结果验证“业务结果校验层”预测。

## 10. Top Failure Observations

1. 4/20 是确定性的无 Evidence 提前停止：D006、D007、D009、D010。
2. 16/20 在相同边界失败：完成 6 次 enrichment 与 1 次 Repository Analyst request 观察，但没有
   completed Agent stage；共同根因尚未被持久化证据证明。
3. 事实级 Context 覆盖仍为 0/23；即使 5 个请求出现同路径候选，也缺少完整事实或必要条件。

这些观察不足以决定 Vector、Hybrid、Rerank，也不能在 Day 11 宣布 Multi-Agent 优于或劣于 Legacy。

## 11. Known Limitations

- 语义复核由 AI 按冻结 expected_properties 完成，`learner_verified=false`。
- Live Dataset v1 没有冻结的 contract_run_success profile。
- 20 个失败路径均缺少完整成功 artifacts；4 个无请求文件是确认零调用，不是日志丢失。
- 16 个请求文件只证明 request boundary 被观察，不证明 HTTP delivery 或 response usage。
- Holdout 仍未运行；2026-09-22 audit-access-exception 原样保留，不能声称严格 blind。

## 12. Day 12 Readiness

Day 11 满足完成条件：唯一一次 20 Dev 已执行；attempts、终态和 request boundary 可追踪；冻结语义
复核与 D001 预测对照已形成；身份完整；unknown/not_comparable 均保留。因此状态更新为
`DAY11 COMPLETED / DAY12 READY`。

Day 12 只能消费这份原始结果做配对分析，不能重跑 Day 11、筛掉失败样本、修改 Prompt/参数或提前
实现 Retrieval 技术。Day 12 必须保留：Legacy task_success=2/20 与本次 0/20 的评分来源差异、
Multi-Agent 20 个产品失败、Token not_comparable，以及 16 个通用失败根因 unknown。

本报告不作以下结论：Multi-Agent 胜过 Legacy；Retrieval 是唯一或主要瓶颈；Vector/Hybrid/Rerank
必须上线；112 条 request observation 等于 112 个已完成或已计费 Provider calls。
