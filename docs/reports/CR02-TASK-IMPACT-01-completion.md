# IMPACT-01：候选影响发现与显式采用

日期：2026-11-02（Asia/Shanghai）。实施基线：`12aa5b736ba3debccc821219983aa0399892bbe2`。
状态：**离线实现、指定独立审查与最终全仓库门禁通过；本地聚焦交付。**
产品 checkout：`C:/Users/50469/specflow-h04-f03-20261023`。
用户已明确批准 [执行单](../tasks/CR02-TASK-IMPACT-01.md) 的离线实现。

## 交付行为

用户可从变更意图和允许快照开始，不必预先给出 targets/checks。发现阶段选择只读工具、
返回候选及缺口；人工逐项 take/edit/exclude 或补充后，宿主在同一事务保存采用记录、
正式 input 和唯一 job。正式资源身份由宿主生成，候选身份不变成 target/check/evidence 身份。

采用支持新建审查和显式修订。未变化目标/check 保留身份，旧输入及报告保留；
全部排除可以仅保存决定，不创建空目标审查。候选失败、中断或尚未完成时不能采用半成目录。
旧人工提供清单的创建/修订路径继续使用原有契约。

发现为独立持久资源，继续使用同一 ReviewWorker、实例锁及一个物理 I/O 槽。
两类队列统一按时间和稳定身份领取、共享 20 条待领取容量；两类预约均检查两个租约。
业务失败不释放未确认的物理调用，迟到结果只结算用量和收尾，不能接受候选或恢复业务状态。
重启分类 interrupted/UNKNOWN，保留已证明的 quiesced，不重新执行调用。

## HTTP 与宿主接线

| 路由 | 结果 |
| --- | --- |
| POST /api/v1/contract-impact-discoveries | 202：只校验、密封、入队，无 HTTP 内模型调用 |
| GET /api/v1/contract-impact-discoveries/{id} | 状态、冻结身份/profile、预算、目录/缺口、错误及派发门禁 |
| GET /api/v1/contract-impact-discoveries/{id}/events | 有界分页元数据，游标绑定本发现 |
| GET /api/v1/contract-impact-discoveries/{id}/events/{event_id} | 可取回的实际投影、动作、工具正文、接受/拒绝及采用详情 |
| POST /api/v1/contract-impact-discoveries/{id}/adoptions | 201：仅保存决定；202：同事务生成正式 input/job |

所有路由沿既有认证、严格字段/查询、Idempotency-Key、1 MiB 请求正文及存储容量边界。
GET 不暴露本地仓库绝对路径。默认不登记发现 profile，也不替用户选择模型或 Provider。

宿主通过 create_app 新参数 `contract_impact_profiles` 显式登记独立 DiscoveryProfile；
`contract_review_profiles` 仍登记正式审查 profile，`contract_review_adapter` 是同一 worker 的
同步 adapter。`discovery_profile(...)` 构造非秘密发现协议，不复用 F01 profile 或其旧费用授权。
本轮只登记 test profiles，并用受控 adapter/MockTransport 验证。

发现请求包含 project_id、change_request、GitSource、authority_bindings、ruleset_usage、
execution_profile_id。GitSource groups 授予已选文件全文读取；authority selector 限定采用规则片段，
不产生其他文件读取权限。project_memory 可显式启用已确认版本，规则版本与正文冻结；
本例使用 ruleset_usage=none，不自动长期化候选或人工排除理由。

候选目录最多 100 项；api_version/endpoint 可未知，local_key 只是模型列表标签，
candidate_id/catalog_hash 由宿主接受后生成。工具目录和 hash 只可选源，SourceRef 必须有
实际请求正文，观察必须已投影。字段身份支持来自引用正文、观察绑定的实际正文或用户意图，
搜索 query 回显不作依据；HTTP path 按完整 token 匹配。

采用请求指定 catalog_hash、全量 dispositions、可选 manual_additions 和 create/revise destination。
每个选中项以从 0 开始的 target_index 对应 destination 的最终 targets；take 不得静默更改
建议，edit 和 exclude 保留理由，人工新增单独标记。最终 target 必须唯一由这些处置解释。
destination 的请求仍接受原 CreateReview/RevisionRequest 校验、CAS、规则适用性及容量检查。

## 原子性、持久化与预算

追加 schema v6 的四张发现/调用/事件/采用表及发现租约列，v1—v5 SQL/checksum 保留。
密封快照沿现有项目归属和字节容量保存；事务前准备字节，事务内重查路径、候选 hash、归属、
正式输入、规则和版本。采用记录/映射、input/job、事件、两层幂等响应同事务提交。
任一步失败整体回滚，包括新快照，不使用“先建 review、再补写采用”的两次提交。

新正式快照的 source_id 由宿主生成；采用校验项目、commit、路径、正文 hash 和角色子集，
不把发现旧 SourceRef 直接搬成正式引用。冻结 input 的 impact_origin 关联采用及映射；
adoption_recorded 事件可完整取回人工修改/排除、新增与正式身份。

发现模型物理调用最多 12、工具动作最多 20、执行最多 300 秒、单次输出最多 8000 Token，
profile 可进一步收紧。非法协议只允许一次连续纠错，相同工具/参数/观察连续三次停止；
一次合法空查询不失败。依赖失败不自动重试，未知模型 usage 阻止下一模型预约。
这些工程上限不是费用授权；未来真实业务链须另批准发现与正式审查的合计费用/调用上限。

## 离线验收映射

静态开发夹具复用 F01 四份正文，增加测试期待和相似名称负控制；定义随测试代码固定，
只在临时案例仓库使用，未改原六例 benchmarks 或其 24 case 身份。
受控模型返回五种角色候选，人工最终只采用文档与示例两个 target/check。

| 出口 | 当前工程证据 |
| --- | --- |
| IMP-01 | 五种角色的候选结构、引用与两目标采用链；相似名称负控制保留在静态材料中 |
| IMP-02 | 越界工具来源、角色扩张、跨项目/目录身份、未知协议字段拒绝；复用密封工具权限边界 |
| IMP-03 | 无依据版本/方法/完整路径拒绝，未知版本保留并仅经人工 edit 补充；空搜索回显不能提供身份事实 |
| IMP-04 | create/revise、身份保留、历史报告、全量处置、同键重放/冲突、事务故障零半成记录 |
| IMP-05 | 实际 HTTP wire 与持久投影一致、原文及观察可见性、未读/伪造引用拒绝、事件分页与详情 |
| IMP-06 | 双向超时保持共享槽、迟到结果不接受、意图保存失败零派发、重启旧 owner 失效、v5→v6 回滚/重入 |

这些是工程协议与执行证据。受控候选的业务内容由测试预先指定，不能证明模型自主召回/
误报、版本归属判断或实际维护收益；这些语义项目保持未验证。完整 B/A/A/C/C、TASK-09、
上下文专项及记忆专项不据此关闭。F01 两次真实失败及 v3 未跑状态保留。

## 独立审查与验证记录

指定 `gpt-6-astra / xhigh` 确认 3 项 P2，修复后限定复核全部关闭。
IAR-02 的第一次修复仍有两条原问题绕过，已继续修复并记录，没有将首次复核写为通过。
首轮全量发现的 SQL 游标生命周期缺陷也已独立限定复核关闭；原三项保持关闭。
详见 [Astra 审查记录](CR02-TASK-IMPACT-01-ASTRA-REVIEW-2026-11-02.md)。

- 首条纵向链：1 passed；第一批 28 passed / 2 测试夹具错误，夹具错误已修复。
- 六文件聚焦：150 passed / 1 旧迁移断言失败，280.37 秒；修正写死版本断言，保留旧 checksum。
- 三项修复及必要正例/旧迁移定向：10 passed，24.85 秒。
- 剩余身份依据反例及必要正例：9 passed，8.75 秒。
- 首轮全仓库：1615 passed / 1 failed / 3 skipped / 2 已有 warnings，555.83 秒，退出1。
  唯一失败为未知usage用例预期USAGE_UNKNOWN、实际EVIDENCE_PERSISTENCE_FAILED。
  已用真实reader/writer连接身份回归稳定复现 SQLite 读锁，查询先耗尽结果后修复，2项定向通过。
- 修复后最终全量：**1617 passed / 3 skipped / 2 warnings，733.63秒，退出0**，共1620项。
  原未知usage节点及新增游标回归均通过；contract_review 的505项全部通过。
- 最终Ruff check/format通过（292文件），git diff --check及文档链接检查通过。
  3项skip均为已有Windows symlink权限条件，2条warnings均为既有TestStrategy收集提示；没有新增skip/xfail。

日志位于 `C:/Users/50469/AppData/Local/Temp/`：
`specflow-impact-focused-20261102-143154-570.log`、
`specflow-impact-targeted-20261102-144908-364.log`、
`specflow-impact-identity-20261102-145621-706.log`、
`specflow-impact-final-pytest-20261102-145835-192.log`（首轮全量失败，保留）。
修复后最终全量：`specflow-impact-final-fixed-pytest-20261102-152722-485.log`（通过）。
原始事务异常：`specflow-impact-diagnostic-20261102-151656-974/transaction-attempt-04.log`。

最终 wheel：`C:/Users/50469/AppData/Local/Temp/specflow-impact-final-build-20261102-152630/specflow_agent-1.1.1-py3-none-any.whl`。
离线构建成功，七个新模块逐字节与当前源码一致；不安装到全局环境。

最终测试使用现有 Python 3.12.10、uv no-project/offline、src 第一/本轮 wheel 元数据第二，
禁用外部 pytest 插件/bytecode。子进程只按名称移除四项 SPECFLOW_LLM 配置，既有 conftest
阻断真实 HTTP，没有读取或打印凭据。未运行真实模型、Holdout 或被查应用，也未部署/推送。

复查命令（产品 checkout 内，使用现有环境，不同步依赖）：

```powershell
$wheel = 'C:\Users\50469\AppData\Local\Temp\specflow-impact-final-build-20261102-152630\specflow_agent-1.1.1-py3-none-any.whl'
$env:PYTHONPATH = (Join-Path (Get-Location) 'src') + [IO.Path]::PathSeparator + $wheel
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
uv run --no-project --offline --python 'C:\Users\50469\AppData\Local\Programs\Python\Python312\python.exe' python -B -X utf8 -c 'import os,pytest; [os.environ.pop("SPECFLOW_LLM_"+name,None) for name in ("API_KEY","BASE_URL","MODEL","TIMEOUT_SECONDS")]; raise SystemExit(pytest.main(["-v","--tb=short","-p","no:cacheprovider"]))'
```

## 文件与后续入口

实现：[发现 schema/profile](../../src/specflow/contract_review/impact_schemas.py)、
[服务与采用事务](../../src/specflow/contract_review/impact_service.py)、
[发现账本](../../src/specflow/contract_review/impact_ledger.py)、
[只读循环](../../src/specflow/contract_review/impact_runner.py)、
[统一调度](../../src/specflow/contract_review/shared_ledger.py)、
[HTTP](../../src/specflow/contract_review/impact_api.py)。

验证：[主链/边界](../../tests/contract_review/test_impact_discovery.py)、
[迁移](../../tests/contract_review/test_impact_migration.py)、
[三项审查回归](../../tests/contract_review/test_impact_review_fixes.py)、
[身份原文依据](../../tests/contract_review/test_impact_identity_evidence.py)。
游标根因回归：[真实读写连接隔离](../../tests/contract_review/test_impact_usage_cursor.py)。

本任务完成后恢复原 F01 人工先导的用户审阅/新试次授权入口。
本交付不自动批准 F01 trial03、其余五例真实批次或任何新费用窗口，不恢复 f01-18 automation。
用户既有 CR02-CURRENT.md 修改保留，只本地聚焦提交本任务；完整路线其余阶段继续按原契约推进。
