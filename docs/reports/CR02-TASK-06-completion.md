# CR02 TASK-06：条件项目记忆 D3-A

日期：2026-11-01（Asia/Shanghai）。实现基点：`5e7c78ae6468b851b4a39ae4da17d527450e3998`。
状态：实现、指定独立审查与最终全仓库离线门禁完成。

## 交付行为

独立发布入口 `POST /api/v1/projects/{project_id}/contract-decisions` 接收严格的
confirm/supersede/withdraw 联合。确认和替代保存完整新正文；撤回仅生成不可变撤回记录。
项目计数器、决定及关系正文、容量账和幂等响应在同一 SQLite 事务提交。成功重放先于
新命令 CAS；陈旧版本、越界或含已移除效力的切片、错误归属、容量或存储失败均不留下半条发布。

provenance 的 declared 分支保存来源声明；review_record 分支核对同项目报告、该报告
答案及同一快照片段。自填 actor_label/claimed_approver 与宿主 actor_subject 分开。
模型输出、本次答案与来源自称批准均不会自动生成项目决定。

切片按有限精确集合判断子集与交集；同维 OR、跨维 AND。只移除被明确替代/撤回的切片，
保留旧规则其余范围。有效视图按指定规则集版本重建；GET 返回原文、base_scope、
removal_slices 和关系身份。列表第一页固定规则集版本，按 (created_at,id) 排序及推进
游标，后页不混入新发布。目标缺必要维度时继续传播 SCOPE_UNRESOLVED。

项目记忆仅由显式注册 profile 的 options.project_memory 启用。关闭时发布/查询返回
OPTION_NOT_ENABLED；未启用的选定 profile 不能使用 applicable_confirmed。
ruleset_usage=none 始终不采用项目规则；applicable_confirmed 必须声明匹配的当前版本，
创建和明确切换版本的 revision 在准备前及提交事务内重核版本。

每目标保存正式决定身份、introduced/adopted 版本、input/snapshot/commit、完整正文与 hash、
来源、精确有效范围及采用原因。仍有效规则跨 review 自动采用，无须再次发布或批准。
新发布不改变 queued/running/完成输入或历史报告。显式 revision 才切换规则集；未声明
规则变化的修订与人工答案派生保持旧集合。规则变化后旧答案明确排除，累计预算继续继承。

v1/v2 父分析及固定复核实际请求携带完整项目规则，强制正文超限时失败，不截尾。
规则授权可进入子任务，但 provenance 不产生额外快照工具权限。报告引用宿主 adoption_id，
宿主补入原文/版本/范围；被替代、撤回、越界或未确定的规则不得作当前支持。

schema v5 追加 project_contract_rulesets 和 project_contract_decisions；旧 v1—v4 迁移
语句和 checksum 保持不变。升级前备份、重入、失败回滚和旧冻结输入字节保留均有测试。

## 验证与审查

| 检查 | 结果 |
| --- | --- |
| contract_review 整组中间门禁 | 346 passed，360.40 秒；收集后又补的最终场景由下面定向和最终全量覆盖 |
| 实际规则支持 v1/v2、修订提交版本竞争 | 3 passed / 13 deselected，9.91 秒 |
| 分页排序修复回归 | 2 passed / 46 deselected，2.56 秒 |
| Astra 原反例与限定复核 | 首轮 1 passed；修复后 2 passed，1.42 秒；唯一 P3 已关闭 |
| 最终全仓库 pytest | **1460 passed / 3 skipped / 2 warnings，343.03 秒**；contract_review 348 项全部通过 |
| 全库 Ruff check / format --check | 通过，272 个 Python 文件 |
| git diff --check | 通过 |
| 本轮离线 wheel | 1.1.1 构建成功，新 decisions.py 已核实打包；分页修复后已重建 |

测试主要位于 `tests/contract_review/test_decision_scope.py`、`test_project_memory.py`
和 `test_schema_migration.py`，覆盖请求联合/上限、认证/查询、归属、CAS/幂等、发布存储
回滚、部分替代/撤回、错误旧规则支持、未知范围与补齐路径对照、历史分页、两个 review
复用、在途冻结、答案派生/规则修订、实际请求/报告/子授权、正文超限和 v4→v5 兼容。

本轮新增 66 项：项目决定 48 项、项目记忆消费/冻结 16 项、迁移 2 项。最终全量统一覆盖
分页修复后的全部代码。3 个跳过均为已有 Windows 符号链接权限条件；2 个警告均为已有
TestStrategy 类收集提示。没有新增 skip/xfail，也没有改旧调度器或旧流程。

独立审查明确使用 `gpt-6-astra / xhigh / fork_turns=none`，确认唯一 P3 排序合同偏差，
修复后同一代理仅复核原发现并关闭。详情：`CR02-TASK-06-ASTRA-REVIEW-2026-11-01.md`。

## 复查命令与日志

环境为现有 Python 3.12.10，uv no-project offline；产品 src 优先，本轮 wheel 提供真实
1.1.1 元数据。关闭外部 pytest 插件及 bytecode，测试子进程仅按名称移除四项 Provider
环境配置；既有 conftest 阻断真实 HTTP。没有改全局安装或新增依赖。

```powershell
$wheel = Join-Path $env:TEMP 'specflow-cr06-final-build-20261101\specflow_agent-1.1.1-py3-none-any.whl'
uv build --wheel --offline --out-dir (Split-Path -Parent $wheel)
$env:PYTHONPATH = (Join-Path (Get-Location) 'src') + [IO.Path]::PathSeparator + $wheel
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
uv run --no-project --offline python -B -X utf8 -c 'import os,pytest; [os.environ.pop("SPECFLOW_LLM_"+name,None) for name in ("API_KEY","BASE_URL","MODEL","TIMEOUT_SECONDS")]; raise SystemExit(pytest.main(["-v","--tb=short","-p","no:cacheprovider"]))'
uv run --no-project --offline ruff check .
uv run --no-project --offline ruff format --check .
```

最终日志：`C:/Users/50469/AppData/Local/Temp/specflow-cr06-final-pytest-20261101.log`。
中间整组及末批日志同目录：`specflow-cr06-focused-20261101.log`、
`specflow-cr06-last-additions-20261101.log`、`specflow-cr06-pagination-fix-20261101.log`。
wheel：`C:/Users/50469/AppData/Local/Temp/specflow-cr06-final-build-20261101/specflow_agent-1.1.1-py3-none-any.whl`。

## 交付边界

本轮只做 TASK-06、本地聚焦提交；不调用真实模型业务通道、不读取凭据、不推送发布。
上述程序证据不替代正式业务语义 AC 的真实输出与独立 oracle。写入、前缀回放、retry
新入口、后续 CLI/展示及旧流程旁支问题继续按各自任务处理，不提前启用。
