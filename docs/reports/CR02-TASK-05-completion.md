# CR02 TASK-05：人工检查点与显式修订

日期：2026-10-31（Asia/Shanghai）。实现基点：`e20d7077d16ada8ecdd4978ede2341679f7e7f53`。
状态：工程实现与全面离线验证完成。

## 交付行为

新增两个认证入口，均沿用 Idempotency-Key、严格 Schema、未知查询参数拒绝及 1 MiB
请求正文上限：

- `POST /api/v1/contract-reviews/{id}/resolution-batches` 接收 select、clarify、
  mark_insufficient 三类互斥答案。核对 review/input/report/question 归属、当前状态、
  expected_version、问题允许的类型及具体选项；任何一项非法整批回滚。
- `POST /api/v1/contract-reviews/{id}/revisions` 接收明确输入或策略变化，保存原始变更
  理由与声明。相同 request、规则使用、有效 profile 或核验选择不能构成空修订入口。

部分答案正式保存，review 保持 awaiting_decision，不派发 job。剩余阻塞按当前报告的
blocking 问题减去同报告持久终局答案计算，查询不改写报告。最后一项阻塞处理后，在同一
事务保存答案、完整新 input、唯一 queued job 和幂等响应，并清空 current_report。
队列、预算、原 profile、存储或事件失败均整体回滚。成功幂等重放先于新命令 CAS；
不同键的并发最后批次最多一个成功。等待裁决释放 worker，后续作业可以继续执行。

答案派生输入继承同一快照、目标、check_manifest、冻结 profile 及累计预算。完整答案、
问题、所选选项、服务主体与自填标签分别保存；父分析与固定复核实际请求均携带完整答案。
v1、v2 均验证长答案尾部没有被摘要截断；本次 review_directives 同样完整进入实际请求。

mark_insufficient 终结阻塞并保留不足；相同材料下不得再次提出同 kind、同目标集合的
阻塞问题，相关工作保持 not_ready、覆盖保留缺口。候选违规时由既有有界校验/纠正链拒绝，
不把缺证伪造为通过。自然语言解释是否充分仍由固定复核及独立业务验收判断。

显式 revision 复用未改变来源的密封字节；来源改变时在事务外准备新快照，再在提交事务
保存快照、输入与 job。未改变的目标和检查项保留宿主身份；变化/排除及其理由留在新输入。
部分已答记录在修订前与旧冻结答案合并，避免遗漏。来源、目标或权威绑定改变时，旧答案
记录为不自动采用；更正需要 supersede_resolution_ids 和明确本次指令，保留原记录。
核验选择继承/清空/重新指定后继续既有逐目标适用性核对。新输入始终从 fresh 路线开始。

schema v4 只追加 resolutions 表及每报告/问题的唯一约束，保留 v1—v3 checksum。
升级前备份、重入、失败回滚和旧输入字节保留均有自动化证据。

## 测试与构建

| 验收边界 | 自动化证据 |
| --- | --- |
| 联合答案、类型/数量/null/未知字段、认证/幂等键/查询 | `tests/contract_review/test_checkpoints.py` |
| 部分答案、末批原子性、CAS/归属/重放、原报告不变 | 同文件 API/DB 集成测试 |
| 队列/余额/profile/末事件失败整体回滚 | 同文件故障测试 |
| 等待释放 worker、重建服务读答案、v1/v2 实际消费与复核 | 同文件受控执行测试 |
| 快照复用/重新密封、修订回滚、检查身份与答案更正 | 同文件修订测试 |
| mark_insufficient 不循环重问，ready/not_ready 正反例 | 同文件报告校验与执行测试 |
| v3→v4 成功/备份/重入/失败回滚，旧迁移路径 | `tests/contract_review/test_schema_migration.py` |
| 既有动态执行、旧 API、CLI 和发布元数据 | 全仓库 pytest |

迁移、上下文和报告分类聚焦 **47 passed，15.91 秒**。新增接口模块共 54 个场景；
首批 45 passed / 1 failed 的唯一失败为测试使用错误历史查询路由，已改正为既有
`/report?report_revision_id=...`。最后受影响定向 **12 passed / 42 deselected，31.18 秒**。
旧最小报告校验上下文未包含 resolutions 的兼容问题已在上述聚焦回归修复并验证。

最终全量 pytest：**1389 passed / 3 skipped / 2 warnings，463.37 秒**；其中
contract_review **277 项全部通过**，新增接口模块 54 项和迁移场景 2 项全部通过。
三个跳过均为原有 Windows 符号链接权限条件，两个警告为原有 TestStrategy 类收集提示；
本轮没有新增 skip/xfail。全库 Ruff check 与 format --check 通过（268 文件），
git diff --check 通过。离线 1.1.1 wheel 构建及检查点模块打包核对通过。

构建：`C:/Users/50469/AppData/Local/Temp/specflow-cr05-final-build-20261031/specflow_agent-1.1.1-py3-none-any.whl`。
全量日志：`C:/Users/50469/AppData/Local/Temp/specflow-cr05-final-pytest-20261031.log`。

复查（PowerShell，在产品目录执行）：

```powershell
$wheel = Join-Path $env:TEMP 'specflow-cr05-final-build-20261031\specflow_agent-1.1.1-py3-none-any.whl'
uv build --wheel --offline --out-dir (Split-Path -Parent $wheel)
$env:PYTHONPATH = (Join-Path (Get-Location) 'src') + [IO.Path]::PathSeparator + $wheel
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
uv run --no-project --offline python -B -X utf8 -c 'import os,pytest; [os.environ.pop("SPECFLOW_LLM_"+name,None) for name in ("API_KEY","BASE_URL","MODEL","TIMEOUT_SECONDS")]; raise SystemExit(pytest.main(["-v","-p","no:cacheprovider"]))'
uv run --no-project --offline ruff check .
uv run --no-project --offline ruff format --check .
git diff --check
```

使用现有 Python 3.12.10；src 优先，本轮 wheel 提供 1.1.1 构建元数据；测试子进程按名称
移除四项 Provider 配置，既有 conftest 阻断真实 HTTP。无新框架或依赖。

## 验收归属

本轮取得 TASK-05 对应 AC-06/07/12—15/24 中人工检查点、输入冻结和原子状态转换的
确定性工程证据；未将其扩张为这些 AC 的全部语义验证。真实模型是否正确理解人工答案、
改进业务判断仍需真实输出与独立 oracle。项目长期决定、写入、回放和 retry 新入口留在
各自后续任务。本轮仅本地聚焦提交，不调用真实模型、不读取凭据、不推送或发布。
