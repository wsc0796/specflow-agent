# TASK-06 恢复记录

## 最终检查点：实现、审查与全量完成

最终全仓库 **1460 passed / 3 skipped / 2 warnings，343.03 秒**，退出码 0；其中
contract_review **348 项全部通过**（本轮新增 66 项）。3 个 skip 与 2 个 warnings 均为
已有条件。最终日志为下述 final-pytest 文件。全库 Ruff check/format（272 文件）、
git diff --check、离线 1.1.1 wheel 均通过。无运行中测试。

完成报告：`CR02-TASK-06-completion.md`；审查报告同下。当前所有工程门禁与原 P3 复核
已完成，交付为本地聚焦提交，不推送发布。后续恢复先查看 `git log -1` 和 `git status --short`。
TASK-06 当前授权范围结束；TASK-07 及其他后续能力按各自任务推进，真实语义 AC 未据程序
结果关闭。以下“运行中”段落是保留的过程记录，不能作为当前状态。

## 全量启动时记录

2026-11-01：Astra 首轮确认唯一 P3（项目决定列表必须按 created_at/id 排序）。
已改为二元组排序/游标并保留固定规则集过滤；主代理 2 passed/2.56 秒，Astra 限定复核
2 passed/1.42 秒，原发现关闭。审查详情见 `CR02-TASK-06-ASTRA-REVIEW-2026-11-01.md`。

整组 contract_review（含当时收集的新增场景）**346 passed，360.40 秒**；日志
`C:/Users/50469/AppData/Local/Temp/specflow-cr06-focused-20261101.log`。整组运行中又补的
实际项目规则支持 v1/v2 与修订版本竞争三项，单独 **3 passed，9.91 秒**；日志
`specflow-cr06-last-additions-20261101.log`。分页修复回归另有上面的两项。最终全量将统一
覆盖所有最终代码与测试，不能把这些数字相加冒充最终测试数。

最新全库 Ruff check/format **272 文件通过**，本轮最终 1.1.1 wheel 已按修复后源码重建。
最终全仓库 pytest 正在终端会话 **65289**；日志
`C:/Users/50469/AppData/Local/Temp/specflow-cr06-final-pytest-20261101.log`。
Python 3.12.10；uv no-project offline；src 第一、当前 wheel 第二提供真实元数据；关闭
外部 pytest 插件/bytecode，测试子进程仅按名称移除四项 Provider 配置，既有 conftest 阻断 HTTP。
当前 HEAD 仍为基点，代码尚未提交，没有推送发布。

下一步：等全量结果，真实失败才定位/补测；通过后同步 completion/CURRENT/任务状态，
git diff --check 并创建本地聚焦提交。没有剩余审查发现，不再扩审或重复已通过门禁。

以下为实施过程记录。

日期：2026-11-01（Asia/Shanghai）。目录：`C:/Users/50469/specflow-h04-f03-20261023`。
基点：`5e7c78ae6468b851b4a39ae4da17d527450e3998`。当前：实现候选完成，离线回归与 Astra 独立审查中。

任务边界见 `docs/tasks/CR02-TASK-06.md`。工作区初始干净；没有独立 TASK-06 单，已按
原规格提取本任务。上下文监督 healthy。不启动学习流程，不改总规格，不新增依赖。
权限：离线测试、本地聚焦提交；不读凭据/不调用真实模型业务通道/不推送发布。
独立审查必须显式使用 `gpt-6-astra / xhigh / fork_turns=none`；完成后限定复核原发现。

## 当前代码与验证

- 新模块 `src/specflow/contract_review/decisions.py`：严格发布/来源联合，项目规则集 CAS/
  幂等/原子写入，历史范围视图及固定版本分页，每目标采用记录。
- `schemas.py`/`store.py`：显式 profile 选项、ruleset_usage 联合、追加 schema v5。
  原 v1—v4 迁移内容不变。旧迁移测试保留原目标，另加 v4→v5 正常/回滚测试。
- `service.py`/`checkpoints.py`：创建与显式采用前后两次核对版本；非规则修订保持旧集合；
  答案派生不升级。更改规则集后旧答案明确排除。
- `api.py`/`main.py`：沿用认证和 1 MiB 正文限制的项目决定 GET/POST。
- `inputs.py`/`dynamic_context.py`/`worker.py`/`report_validation.py`/`execution.py`：
  完整项目规则进入实际请求、子授权投影、固定复核和宿主报告；失效规则不作当前支持。
- 新测试 `test_decision_scope.py`、`test_project_memory.py`；首批发布场景 46 通过/1 夹具
  失败；第二轮 73 通过/2 夹具失败（重复 repository_path），已修正夹具。此前执行测试的
  投影字段名和暂停超时也已修正。没有据这些中间结果宣称最终门禁通过。
- 正在运行整组 contract_review：终端会话 15636，日志
  `C:/Users/50469/AppData/Local/Temp/specflow-cr06-focused-20261101.log`。
  末批新增三项独立运行：17724，日志 `specflow-cr06-last-additions-20261101.log`。
- 本轮离线 wheel 构建成功：
  `C:/Users/50469/AppData/Local/Temp/specflow-cr06-final-build-20261101/specflow_agent-1.1.1-py3-none-any.whl`。
  当前 Ruff check/format 通过；全仓库门禁尚未执行。

独立只读审查代理 `/root/task06_astra_review` 已显式创建：`gpt-6-astra / xhigh / fork_turns=none`。
审查范围为上述固定 base 到当前工作区差异（含未跟踪新模块/测试）。产品代码已冻结等待审查。
上下文监督本轮两次均 healthy。下一步：查看定向结果/审查，修复确认缺陷并限定复核，
最终全仓库 pytest、Ruff、文档同步、本地聚焦提交。不推送发布。
