# CR02 TASK-08：显式重试、有限因果前缀回放与故障验证

日期：2026-11-02（Asia/Shanghai）。实施基线：`a7b6f64291d0ffdb4d15f59af9c5c6ed96fb73d2`。
工程交付完成：2026-11-03；[完成记录](../reports/CR02-TASK-08-completion.md)、[任务进度](../reports/CR02-TASK-08-progress.md)。
用户本轮明确要求完成 TASK-08 并核实任务进度；该授权取代 v0.2.4 中本轮暂不实施 TASK-08 的安排。
任务含 COMMON fresh 与已选择 D5-C/OPT-REPLAY；其余既有边界保持。

## 来源与范围

依据 [v0.2.2 总合同](D:/Downloads/agent学习/AI_HANDOFF/2026-10-29-GPT讨论交接/SPEC_FLOW_CONTRACT_MAINTENANCE_DRAFT_v0.2.2.md)
C§5.1–5.6、§6.4、§8.5，D TASK-08，AC-12/13/15/22/24/26/27，以及同目录定向勘误。
沿用唯一产品 checkout、单实例/worker、冻结输入、累计预算及持久派发门禁。

- 新增 `POST /api/v1/contract-reviews/{review_id}/retries`。严格请求包含 expected_version、
  failed_job_id、input_revision_id、reason、mode；reuse_completed 必填 recovery_fallback，fresh 禁止该字段。
- 幂等成功重放先于 CAS/当前状态；仅允许当前同输入的最近 failed/interrupted job。
  同输入新建 job/attempt，保留 retry_of、requested/effective_mode、fallback、边界和原因，不新建 input。
- fresh 从头新调用；reuse_completed 从起点按顺序验证已持久接受的完整前缀。
  自然未完成后缀从断点新执行，一旦进入新后缀不再寻找旧命中。
- 损坏/不可核对前缀使用客户端预选 stop 或 restart_fresh；后者不重置时钟、已发生调用或累计账。
  profile 不可执行、权限或归属错误不能通过 fallback 绕过。
- 支持完整只读子结果与完整父验收步骤构成的前缀单元；父验收前中断不复用半截子树。
  partial/rejected 保留原文和验收语义，不新增自然语言到硬权限的推导。
- 查询、事件和薄 CLI 展示 retry/复用来源与边界；原 waiting/queued、迟到、预算和旧执行者保证继续成立。

## 实现接点与兼容决定

允许修改 `src/specflow/contract_review/`、直接相关薄 CLI、相应测试和任务报告；不新增依赖。
新增聚焦 retry/replay 模块。既有 schema migration 不修改，只追加必要 replay binding 迁移。
默认 profile 的 replay 仍关闭，显式 v2 profile 才开启；v1 保持已有指纹及 fresh 路径。

回放为新 job 的逻辑步骤及 binding/receipt，关联原 step/call/结果并保存完整性、前序与兼容身份；
不伪造新物理 call，不重新占模型次数或结算旧 usage。原历史不可变。
当前 attempt 的子结果 resolver 合并原生子记录与验证后的绑定，保留旧稳定 result_ref，
不违反原 child_tasks.result_ref 的全局唯一约束，也不将旧 job 记录冒充新 job 原生记录。
实际完整请求按原样比较，不删除 job/时间/预算字段制造命中。

### 2026-11-02 B 方案补充：模块边界与执行语义

用户在侧聊评估收益与代价后要求同步本补充。沿用当前实现和 T08-01—09，不新增功能范围、依赖或额外验收轮次；已满足的条款直接核对已有实现/测试，只补实际缺口。

- **模块依赖**：保留一个业务执行循环及一个真实派发入口。回放解析器只取得必要的存储、执行权/权限校验与 binding 记录接口，不持有完整 Worker、Provider 或网络客户端；共享账本继续统一预算与执行权。优先收紧现有构造依赖，不要求拆成两套完整执行流水线，不把代码依赖隔离表述为进程级安全隔离。
- **明确判定**：分别表达命中、正常新后缀、前缀损坏/无法核对、权限或归属拒绝。可用明确类型、枚举或专用异常；不为形式新增抽象层，普通空返回只能表达明确的正常未命中，不能吞掉损坏或越权。
- **阶段与模式**：requested_mode 保留用户选择，执行阶段区分前缀回放与新后缀。命中步骤零新物理调用；reuse_completed 的正常新后缀允许通过统一门禁新派发。一旦进入新后缀，不再寻找旧命中。所有 fresh、新后缀和 restart_fresh 的真实调用复用同一预算、槽位、持久化及执行权检查。
- **边界分类（T08-04/05/06）**：正常尚无合法接受结果，且符合在途收尾要求时，开始新后缀；已接受前缀正文/关联损坏，或完整请求、前序、build 等无法证明兼容时，按预选 fallback 处理；非法权限/归属直接拒绝，原 profile 不可执行要求 revision。不能把所有请求不匹配都自动当作正常后缀，也不能把自然缺少后缀当作损坏。
- **fallback 状态**：restart_fresh 在同一 attempt 重建业务上下文、执行游标与当前有效复用视图，保留此前回放和放弃记录供追查；不得混用旧复用状态和从头生成结果。deadline、累计用量及已发生资源开销不重置。
- **事务范围**：受理时原子创建 job 与幂等响应；回放步骤的最终校验和 binding 接受使用短事务。新调用先提交意图/预算，事务外执行 Provider/工具 I/O，再提交结果。受理失败不留新 attempt；202 之后的匹配失败如实记录在已受理 attempt，不能伪装成从未创建。
- **不可变范围与结算（T08-08）**：原已接受请求/结果正文及来源不改写；调用生命周期、UNKNOWN 收尾和可靠 usage 允许受控维护。预算使用已确认实耗加未结算预留，同一 call/维度的重复证据不重复累计；本地 quiesced 不自动清零远端未知预留。承诺是命中步骤零新派发、历史 usage 不重复计入，不承诺供应商实际费用不重复。
- **复用资格**：普通模型/工具步骤要求合法、完整、已持久接受；父方验收回执要求仅用于完整委派复合单元，partial/rejected 的合法决定按原样保留。input_revision_id 与 input_hash 分开；指纹用于完整性与兼容核对，不声称仅靠 hash 即不可篡改。首版可保留严格 build 相等策略，接受跨 build 复用率降低，不新增语义兼容映射系统。

验收优先映射已有测试：T08-01 检查成功响应丢失后同键重发仍返回原响应；T08-03/04 按实际阶段核对零派发和新后缀派发；T08-05 检查正常缺失与损坏的不同分支及 fallback 状态重建；T08-06 检查复用接受时的执行权/权限；T08-08 检查重复/部分/迟到 usage 与槽位的独立处理。现有用例已覆盖时不补镜像测试。
本补充不要求新增 Schema 迁移或接口；若收紧模块边界确需扩大原合同范围，先说明具体原因和增量代价，不自动做更大重构。

## 验收矩阵

| ID | 必须成立的程序行为 |
| --- | --- |
| T08-01 | fresh 严格字段、认证、未知查询/字段、同键重放、异载荷冲突、CAS、跨 review/input/旧 job、completed 拒绝；失败不留下新 job/版本/幂等成功记录 |
| T08-02 | 同 input 新 job 与来源可查，输入/profile/快照不变；累计额度、在途槽、queued/waiting 保持；profile 漂移拒绝且不静默替换 |
| T08-03 | fresh 实际新派发；reuse 的有效完整模型/工具前缀零新物理调用，逐项来源可查，旧用量不重复结算 |
| T08-04 | 意图-only/未接受/正常尾部缺失是新后缀；首次新后缀后不回旧后缀命中；实际请求或前序变化使旧后缀失效 |
| T08-05 | 已接受记录正文/hash/投影/关联损坏、兼容 build 不可核对，分别验证 stop 与 restart_fresh；无跨坏点拼接，fallback 不重置预算/时钟 |
| T08-06 | 当前权限、版本、source selector 与 result 归属复查；跨 review/input 或权限失败不使用 fallback 扩权 |
| T08-07 | 完整子结果＋持久父响应/验收才可作为单元复用；只有子结果、只有父请求、未接受/晚到父响应均不获得单元资格；partial/rejected 不改写原文或扩大用途 |
| T08-08 | 重复 retry/迟到与收尾不释放其他实例槽；UNKNOWN、本地 quiesced、usage 分离；新 attempt 依赖重试域独立，review 累计次数不清零 |
| T08-09 | additive migration、旧资料可读/重复迁移、容量/存储回滚、旧 API 与 v1 profile 兼容；CLI 按公开请求合同调用，不执行外部 procedure |

使用已有受控 adapter/MockTransport、隔离 SQLite 与 Git 夹具，不连接真实业务端点。
T08-03/04/07 同时保留同一冻结输入、固定故障点的 fresh/reuse 对照：实际新增 Provider 派发、
工具执行、复用来源、最终报告与累计用量；无法比较时只保留观测值，不计算改善比例。
升级简历 Claim 仅在上述实现、门禁和同一独立审查均通过后登记，不另建评测平台。
先运行相关新测试，最终候选完成一次全仓 pytest、Ruff check/format、diff 检查及独立代码审查。
独立审查由 gpt-6-astra / xhigh 在本任务同一轮覆盖 B 方案边界及新增简历 Claim；有实质问题再限定复核，不为本补充另开整库审查。
有实质问题则修复并复核；不以已有程序 PASS 关闭业务语义或费用收益验收。

## 交付与停止边界

完成报告记录验收映射、命令与实际结果、固定提交及未测范围。做本地聚焦提交，不推送。
保留并排除用户已有 `docs/reports/CR02-CURRENT.md` 修改。
不实现通用 DAG/执行栈恢复、主动取消、任意进程强杀、业务写入、副作用 exactly-once、
候选发现 retry 或跨 trial 缓存；不读取凭据/Holdout，不启动业务模型/收费探针、旧 automation。
真实模型效果、实测费用、E03 原场景及 TASK-09 全量验收各保留其独立状态。
