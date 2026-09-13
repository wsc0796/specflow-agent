# Evaluator Contract v1

- contract_id：`SF-EVALUATORS-v1`；version：`v1`；日期：2026-09-13。
- status：`FROZEN-v1 / AI-prepared / learner-reviewed-boundaries`；对应 [Eval Contract](eval-contract-v1.md)。
- 实现基线：`5f2815d`；学习者决定见 [Day 8 证据卡](evidence/day-08.md)。
- 本文定义文档级 evaluator ID；不声称已注册同名 Python 类、入口或统一执行器。
- 所有 should_pass/should_fail 均为 AI 起草的 **calibration fixture specifications**，
  只描述判定属性；Day 9 才实现 fixtures，今天不生成正式任务、Gold 或 Holdout 内容。

## 1. 公共输入输出协议

每项记录 evaluator_id/version、inputs、outputs、method、decision、should_pass、should_fail、
blind_spots、human_review、implementation_status 和 evidence。评分不可省略前置条件与证据来源。
统一输出草案：case_id/run_id、evaluator_id/version、product_terminal_state、
evaluator_status（valid/incomplete）、verdict（pass/fail/unknown/N/A）、value/unit、
findings、evidence_locators；比较层另给 comparable/not_comparable/N/A。
“valid”只表示本次评价有足够输入可执行，既可能 pass 也可能 fail。
原始 finding/status 必须保留，不能把旧实现包装成已经支持新协议。
缺失遥测/Gold/运行证据只影响对应 evaluator；不伪造产品 failed，不把 unknown 转为 0。
已证实违反属性时 fail；证据不足时 unknown；属性不适用时 N/A，均记录原因。
语义指标依赖 Evaluator-side Gold/answerability；这些字段不得进入被测模型。

## 2. 实现盘点

| evaluator_id | method | implementation_status | 当前可证明范围 |
| --- | --- | --- | --- |
| contract_run_success | deterministic | existing_core / wrapper unknown | portfolio benchmark 的 artifact/终态/计数合同 |
| source_reference_validity | deterministic | existing_core / wrapper unknown | sources 路径合法性与存在性 |
| token_cost_completeness | deterministic（拟定） | contract-only / unknown | 已有 Token 字段与聚合，不存在已证明的完整性 evaluator |
| fact_evidence_coverage | human-reviewed mapping + deterministic ratio（拟定） | contract-only / unknown | 事实级 Gold/scorer 未建立 |
| citation_support | human（拟定） | contract-only / unknown | 现有路径检查不能完成 claim 支持判定 |
| task_success | human rubric（拟定） | partial primitives / scorer unknown | Rubric 与 0/1/2 分数模型存在 |
| safe_abstention | deterministic trace + human semantics（拟定） | partial runtime / evaluator unknown | 无 Evidence 提前停止分支存在 |

前三项是确定性评测合同候选，其中只有前两项有现成核心判定；不凑出“三个已实现”。
完整 10 条 Behavior Suite 的统一 evaluator/执行入口为 unknown，导航见
[源码 Evidence Pack](evidence/day-08-source-pack.md)，本日不补产品实现。

## 3. contract_run_success

- version：`v1`；profile：`portfolio_multi_agent_mock@5f2815d`。
- inputs：一次 benchmark run 的七项 required artifact 路径、manifest.json、metrics.json、
  case_id/category；profile 与仓库/代码 revision。不同 topology 不静默复用固定 6 的规则。
- outputs：当前 _read_run 的 status、schema_validated、error_codes；目标公共协议另保留原始结果。
- method：deterministic；implementation_status：existing_core，统一 wrapper 为 unknown。
- decision：required 文件存在且不是 symlink；manifest/metrics 可解析为 JSON object；
  workflow_state=completed 且 schema_unvalidated_count=0、schema_validated_count=6 才 passed。
  文件/解析错误为 benchmark_artifact_invalid；其他不满足为 benchmark_contract_failed。
- aggregation：profile 内 passed/attempted；零尝试目标为 N/A。当前 _rate 返回 0.0，保留差异。
- should_pass：所需文件具备，两个 JSON object 合法、完成态和计数满足；内容即使偏题，
  仍可通过此窄合同。它是用于显露盲区的 fixture 属性，不是 task_success 正例。
- should_fail：删除一项必需文件，或保持文件但使完成态/Schema 计数不满足；分别核对 finding。
- blind_spots：不核查 requirement 完成、事实正确、引用支持、真实 Provider 调用或所有 artifact 内容；
  除 manifest/metrics 外，当前 required 文件只在该函数检查存在/非 symlink。
  evaluator 环境丢文件与产品未生成文件在当前错误码中没有完整归因区分。
- human_review：检查 profile 是否适用、缺件来源、以及读者是否把 contract pass 写成需求成功。
  跨 profile 比较前审查指标口径；产品路径完成与内容质量分开裁决。
- evidence：`src/specflow/evaluation/benchmark.py:164` 的 _read_run；`:188`–`:203` 判定；
  `:207` 聚合、`:262` 的 _rate；`tests/test_benchmark.py:98` 的
  test_benchmark_cli_writes_report_and_baseline 在 `:118`–`:120` 验证报告。
- calibration：最小缺件、错误状态、计数不匹配、偏题但结构通过的 fixtures 待 Day 9；今天未运行。

## 4. source_reference_validity

- version：`v1`；profile：`legacy_sources_path_check@5f2815d`，含非空来源前置条件。
- inputs：sources.json 解析值和可信 repository_root；文件来自固定 revision，读取权限正常；
  candidates 取 selected_files、matched_files 与 excerpts[*].relative_path 的并集。
- outputs：当前 helper 向 findings 添加 sources_invalid、source_evidence_missing、
  source_path_external、source_path_missing；目标 pass/fail 只由该 evaluator 的 findings 归纳。
- method：deterministic；implementation_status：existing_core，公共输出 wrapper 为 unknown。
- decision：输入为 dict、存在候选；去重后路径非 absolute、不含父目录段；resolve 后在 root 内，
  且 is_file。非 dict/空候选/越界/不存在按已有对应 finding 判 fail。
  这不是 Tool Permission 的全部策略，也不保证当前 helper 对任意畸形嵌套输入均正常返回。
- should_pass：输入形状符合约定、非空相对路径解析在 root 内且存在；不要求文件支持某一主张。
- should_fail：同样输入形状下，一个候选越过 root，或在 root 内但不存在；分别核对两类 finding。
- blind_spots：未核查行号、symbol、内容 hash、repository revision 一致性、主张语义支持、
  摘录条件完整性或敏感文件全部政策。路径有效也可能对应错误 revision/错误事实。
  字符串等畸形容器、路径运行环境异常的完整分类为 unknown，不能宣称全面 schema validator。
- human_review：抽查固定 revision 的实际引用与输出 claim；区分“来源合法”与“支持结论”；
  若 no-answer case 合法无来源，需另选 profile/N/A，不能删空来源 finding 来调通过率。
- evidence：`src/specflow/evaluation/validators.py:200` 的 _validate_sources；
  `:204`–`:208` 候选来源、`:213`–`:231` 路径检查；`:75` 为 validate_artifacts 接线。
  `tests/test_live_validation_import.py:77` 的
  test_live_import_rejects_missing_artifact_invalid_json_external_path_secret_and_traces，
  `:98`–`:101` 断言 source_path_external；fixture 正常导入测试在 `:60`–`:66`。
- calibration：path-valid-but-unsupported、越界、缺失和非适用无答案条件仅列属性；Day 9 实现。

## 5. token_cost_completeness

- version：`v1`；profile：`all_attempted_provider_usage`。
- inputs：独立 attempted-run 清单、所有实际 Provider 调用/重试记录、每调用 input/output usage、
  usage 来源与存在性、零调用证明、terminal 信息、计数协议版本；不以 passed 过滤。
- outputs：complete_run_count、attempted_run_count、telemetry_coverage、unknown_run_count、
  observed_subtotal、full_total、unknown reason；比较侧另输出 not_comparable。
- method：deterministic（拟定）；implementation_status：contract-only / unknown。
- decision：每个 attempted run 的全部调用可核对且 usage 是已观测的合法非负整数，
  或已证明零调用，才 complete；布尔值/缺失/非法/估算冒充实测均不能算完整。
  coverage=complete_run_count/attempted_run_count；零尝试为 N/A，尝试清单未知则 coverage=unknown。
- verdict：全部 complete 为 pass；已知存在缺失为 completeness fail 且成本 value=unknown；
  无法判断清单完整性时 verdict=unknown。这里的 fail 不是产品运行失败。
- should_pass：failed/degraded run 也有全部请求的合法 usage；或可证明 Provider 未被调用的 0。
- should_fail：Provider 已被调用但某请求 usage 缺失；或只交 passed 子集，遗漏其他 attempted run。
  若连独立尝试清单都不可得，预期为 unknown，而不是用已收到的记录算 100%。
- blind_spots：完整字段不自动证明 Provider 报数真实；请求清单若漏项可能造成伪完整；
  不同 tokenizer/usage 口径、缓存和 reasoning token 定义未核对时无法跨模型直接比较。
- human_review：核对独立尝试清单与请求计量来源、零调用证据、重试去重和缺失归因；
  任一侧 incomplete 时禁止完整 Token 排名，保留 observed subtotal 和其他质量结果。
- evidence：`src/specflow/evaluation/benchmark.py:200`–`:202` 读取计数；`:219`、`:238`–`:239`
  为 passed-only 聚合；`:258`–`:259` 缺失回退 0；`src/specflow/evaluation/metrics.py:51`–`:53`
  为默认数值字段。以上是待补足基础，均不是 completeness 实现。
  `tests/test_agent_adapter.py:60` 的 test_runner_propagates_real_response_usage 在 `:70`
  检查 usage 传递；`:72` 的兼容测试在 `:90` 检查 0，不证明 0/unknown 已分离。
- calibration：完整失败 run、确认零调用、缺失 usage、遗漏 attempted run 的 fixture 属性待 Day 9。

## 6. fact_evidence_coverage

- version：`v1-hypothesis`；inputs：固定 revision 的事实级 Gold、answerability、
  目标组件最终 Context、fact-to-excerpt 映射和必要前提、Gold/scorer 版本。
- outputs：matched_fact_ids、missing_fact_ids、eligible_count、matched_count、coverage、
  unknown/N/A 理由及逐项证据定位；所有中间计数保留。
- method：human-reviewed fact mapping + deterministic ratio（拟定）；implementation_status：unknown。
- decision：仅在 answerable 且 Gold 完整时，计算已被 Context 完整支持的不同 Gold fact 比例；
  缺失事实计未命中，重复片段不重复计数；必要条件被截断不算完整支持。
  answerable 空 Gold 为 unknown；unanswerable/safety_reject 为 N/A；无 Context 证据为 unknown。
- should_pass：fixture 所有适用事实及条件都能在指定 Context 对照定位，预期 coverage=1；
  不据此推定真实任务质量的通过阈值已冻结。
- should_fail：文件被 selected 但唯一所需事实没有进入 Context，预期该事实未命中；
  这是评分正确性的校准反例，产品总体 verdict 阈值仍 hypothesis。
- blind_spots：Gold 遗漏/错误、条件粒度不一致、事实映射主观、Context 观察点不准确；
  文件路径移动与事实覆盖变化要分别解释，不能只按字符串路径相等评分。
- human_review：审查事实原文/必要条件、revision、映射理由与分歧；不以模型自评替代 Gold。
- evidence：`src/specflow/evaluation/models.py:29` 的旧 Case 没有事实级 Gold schema；
  `src/specflow/evaluation/metrics.py:61`–`:63` 是文件计数；
  `src/specflow/evidence/collector.py:89`、`:109` 和 `src/specflow/evidence/models.py:117`
  提供观察基础，完整 scorer 与校准测试为 unknown。
- calibration：Day 9 准备映射 fixtures；T0 数值 unknown/hypothesis，后续仅按 Dev 纪律校准。

## 7. citation_support

- version：`v1-hypothesis`；inputs：需要证据支持的输出 claims、逐 claim 引用、固定 revision
  的来源片段与条件、映射规则/标注版本；不把 answerability 提供给执行模型。
- outputs：supported/unsupported/unknown claim 集、支持比例、遗漏引用数、逐 claim 理由；
  无需核查的 claim 集为空时 N/A，不输出满分。
- method：human（拟定），未来是否引入 LLM judge 须单独校准；implementation_status：unknown。
- decision：引用来源可验证且足以支持该 claim 的语义与适用条件才 supported；
  文件存在但不支持 claim，或应引用却没有引用，为 unsupported；原证据不可得为 unknown。
- should_pass：claim 的范围与引用事实、条件一致，审阅者能指出支持位置。
- should_fail：合法文件路径配上不受该文件支持的 claim，或把条件结论泛化成无条件结论。
- blind_spots：跨文件隐含关系、拆分 claim 粒度、否定语义、人工偏差与评分者先看答案造成偏置。
- human_review：先核主张和来源，再记录支持/反证及分歧；source_reference_validity 只作前置检查。
- evidence：`src/specflow/evaluation/validators.py:200`–`:231` 只校验来源路径；
  `src/specflow/evaluation/rubric.py:15` 声明人工维度，不是语义 Citation scorer。
  独立实现、标注一致性证据与校准测试均为 unknown。
- calibration：支持/不支持/条件丢失/证据不可得的属性留作 Day 9 fixtures，不含正式任务内容。

## 8. task_success

- version：`v1-hypothesis`；inputs：requirement、Evaluator-side expected_properties/forbidden_claims、
  输出产物、事实证据、适用终态、评分锚点、固定版本；不使用单一 run_success_rate 替代。
- outputs：逐属性满足/违反/unknown、任务 verdict、人工维度 0/1/2 与理由、证据定位。
- method：human rubric（拟定）；implementation_status：已有 Rubric/Score primitives，统一 scorer unknown。
- decision：所有适用必要属性有证据满足且无已证实的禁止主张，才可判 task pass；
  明确违反必要属性则 fail；不足以判断时 unknown，不拿 Schema 完成态补齐。
- should_pass：任务要求的可观察输出属性均满足，相关事实、风险和限制有足够证据。
- should_fail：结构和 Schema 通过，但遗漏一个必要属性或给出明确禁止的错误主张。
- blind_spots：expected_properties 不完整、评分锚点过宽、人工猜测隐含需求、多个维度重复计分；
  小型 Golden Suite 不支持细微生产提升的统计结论。
- human_review：逐属性审查、记录反例和分歧；人工分与自动 finding 分开，不用总分掩盖关键失败。
- evidence：`src/specflow/evaluation/rubric.py:15`、`src/specflow/evaluation/models.py:73`；
  `tests/test_evaluation.py:45` 验证分数范围，`:78` 验证 Mock 与 human_scores 分离；
  `src/specflow/evaluation/multi_agent_runner.py:73`、`:83` 的 requirement_coverage 是固定 0。
- calibration：评分锚点/最小违反属性 fixtures 待 Day 9；真实任务 Gold 与一致性校准目前 unknown。

## 9. safe_abstention

- version：`v1-hypothesis`；inputs：Evaluator-side answerability、Gold/安全约束、输出、
  终态/错误码、实际 Tool/Agent 调用证据、适用模式与 policy 版本。
- outputs：拒答适用性、是否虚构、行为约束 verdict、终态证据与 unknown 原因。
- method：deterministic trajectory checks + human semantics（拟定）；完整 evaluator 为 unknown。
- decision：仅在该任务确应拒答/安全拒绝时，按预声明语义与行为属性评估；
  EVIDENCE_NOT_FOUND 只证明本次零摘录路径触发，不能证明仓库确实不存在答案。
  不同路径的合法终态须单独绑定，不把所有拒答强制映射 completed。
- should_pass：任务适用拒答，输出没有编造事实，实际行为和预声明终态符合对应路径约束。
- should_fail：实际有答案却因漏检拒答，或无答案时编造出处；相关证据缺失则 unknown。
- blind_spots：错误 answerability、检索漏选伪装成无答案、只有静态文案而无实际行为证据；
  Mock 的安全路径结果不能证明真实模型面对注入的行为。
- human_review：核对固定 revision 下的可回答性，区分 retrieval failure、正确拒答与权限拒绝。
- evidence：`src/specflow/runner_multi.py:130`–`:142` 的零 excerpt 提前停止；
  `tests/test_cli_multi_agent.py:76` 的 test_zero_evidence_fails_before_agents_and_persists_reason
  在 `:116`–`:126` 检查调用/终态/错误码。语义拒答 scorer 与统一行为套件为 unknown。
- calibration：适用拒答、漏检导致错误拒答、编造出处、缺行为证据的属性待 Day 9 fixtures。

## 10. Review、版本与本日停止线

上述 fixture specifications 与正式 20 Dev + 10 Holdout 分属不同用途；教材合成内容也不并入。
评价方法、Gold 规则、锚点、缺失处理或阈值变化均需要新版本和变更理由，不覆盖旧结果。
学习者已 Review 路径/语义拆分、三值聚合、0/unknown、合法失败与 Behavior pass 等
关键边界。AI 起草和代码定位不算学习者独立设计证据；contract-only/unknown 条目
冻结的是目标语义和证据缺口，不冒充已有实现或已校准。
本文不授权创建 fixtures、访问 Holdout、跑 baseline、改代码或推进下一日。
本次核验仅涉及文档结构、引用/链接和空白差异，未执行产品测试或评测。
