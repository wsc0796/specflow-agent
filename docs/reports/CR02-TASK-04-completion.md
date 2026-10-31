# CR02 TASK-04：动态取证、一级委派与 Provider 适配

日期：2026-10-31（Asia/Shanghai）。实现基点：`ff923daaf87051504589ea2afb7906398a5ae0d3`。
状态：工程实现与全面离线验证完成。

## 交付行为

显式注册 `dynamic_profile()` 的 v2 引擎后，父分析按证据缺口选择只读工具、一级子任务或
直接提交报告。报告仍须固定复核，最多一次返工。v1 冻结 profile 和受控执行路线保留，
默认应用不会选择 Provider。

五个工具只访问密封快照：`list_sources`、`search_sources`、`read_source`、
`inspect_python_contract`、`inspect_json_contract`。工具参数严格校验，区分空结果、
依赖失败、不支持和截断；来源目录不算正文已读。行片段可连续合并覆盖，JSON 指针仅包含
所选子树，工具授权和报告引用使用同一覆盖判断。Python 只作有限语法分析；JSON 只解析
明确允许的本地引用。导入和实例重绑定、相对或未解析导入不再被误认成确定 FastAPI 路由。

两项登记能力支持一级、顺序、最多两次委派。子工具权限取能力与材料片段允许集的交集；
规则或观察引用不会扩张来源读取权。父、子、固定复核与物理重试共享账本；子另外受模型、
工具和期限上限限制。无进展和非法动作均有界停止，非法工具提议计账但不派发工具 I/O。

宿主先接受子结果，父下一合法 action 显式采用、部分采用或拒绝；首次验收与该 action
在同一事务落盘，之后才执行新 I/O。完整子正文与证据历史保留，肯定结论只使用已发布且
合格的子证据。最终报告汇总必须与最新父验收一致；partial 的语义用途交给固定复核检查。

同步 OpenAI-compatible adapter 在冻结 profile 校验后才发出一次 HTTP 请求，实际 wire
payload 与持久化请求投影一致。响应按块读取，上限 128 KiB；错误分类、未知/部分用量和
最多一次宿主物理重试均有记录。未知或迟到调用保留执行槽直至本地收尾，迟到正文不接受。
临时存储失败阻断新派发，恢复后先收尾原作业；未知宿主异常尽力落盘失败状态。

schema v3 追加 action、child_task 表及 steps.body，保留 v1/v2 checksum。升级前备份、
重复迁移、旧排队输入/步骤保留和 DDL 失败整体回滚均覆盖。

## 验收证据

| 边界 | 自动化证据 |
| --- | --- |
| 工具参数、材料范围、分页/截断、JSON local-ref、静态支持边界 | `tests/contract_review/test_dynamic_tools.py` |
| 规则原文、观察投影、子证据发布/采用、v1 指纹 | `tests/contract_review/test_dynamic_context.py` |
| 最终 payload、零派发、流式上限、状态/异常、严格用量 | `tests/contract_review/test_dynamic_provider.py` |
| 直接提交/工具路线、关闭/嵌套/顺序委派、共享预算与子期限 | `tests/contract_review/test_dynamic_workflow.py` |
| 父验收事务、完整子结果、汇总一致、迟到拒收与存储恢复 | `tests/contract_review/test_dynamic_workflow.py` |
| v1→v3、v2→v3、回滚/重入与旧数据读取 | `tests/contract_review/test_schema_migration.py` |
| 报告规则/引用、旧 HTTP API 与已有运行生命周期 | contract_review 模块及全仓库 pytest |

本次接手补充的 22 项定向检查：**22 passed，58 deselected，8.45 秒**。先复现静态
绑定误报（9 failed / 1 passed），修复后这些反例与正例全部通过。

首次完整模块结果为 220 passed / 1 failed（173.49 秒），暴露宿主异常收尾的可见性窗口：
失败记录可见时，停止派发标志尚未设置。修复为先停止派发、再落盘失败；回归以事件固定
该窗口，并检查后续排队作业保持 queued。故障与存储恢复/生命周期回归 **14 passed，
27.86 秒**。

最终全仓库 pytest：**1333 passed / 3 skipped / 2 warnings，193.79 秒**，其中
contract_review **221 项全部通过**。三个跳过均为已有 Windows 符号链接权限条件；
两个警告为已有 TestStrategy 类收集提示。本轮没有新增 skip/xfail。
全库 Ruff check 与 format --check：通过（266 个 Python 文件）；`git diff --check` 通过。
离线 wheel 构建成功，版本 1.1.1，全部 9 个新增模块已核实打包。

构建：`C:/Users/50469/AppData/Local/Temp/specflow-cr04-final-build-20261031/specflow_agent-1.1.1-py3-none-any.whl`。
模块日志：`C:/Users/50469/AppData/Local/Temp/specflow-cr04-contract-review-20261031.log`。
最终全量日志：`C:/Users/50469/AppData/Local/Temp/specflow-cr04-final-pytest-20261031.log`。

验证使用现有 Python 3.12.10、`uv run --no-project --offline`；当前产品 `src` 为
PYTHONPATH 首项，本轮 wheel 位于其后提供实际 1.1.1 构建元数据。关闭外部 pytest 插件及
bytecode，在测试子进程按名称移除四项 Provider 环境配置，既有 conftest 阻断真实 HTTP。
完整复查命令（PowerShell，产品目录执行）：

```powershell
$wheel = Join-Path $env:TEMP 'specflow-cr04-final-build-20261031\specflow_agent-1.1.1-py3-none-any.whl'
uv build --wheel --offline --out-dir (Split-Path -Parent $wheel)
$env:PYTHONPATH = (Join-Path (Get-Location) 'src') + [IO.Path]::PathSeparator + $wheel
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
uv run --no-project --offline python -B -X utf8 -c 'import os,pytest; [os.environ.pop("SPECFLOW_LLM_"+name,None) for name in ("API_KEY","BASE_URL","MODEL","TIMEOUT_SECONDS")]; raise SystemExit(pytest.main(["-v","-p","no:cacheprovider"]))'
uv run --no-project --offline ruff check .
uv run --no-project --offline ruff format --check .
git diff --check
```

未新增框架或依赖，未改全局安装或旧测试预期。

## 验收归属和下一步

本轮提供 AC-10/11/16/21/24/25/27 中动态执行、权限、预算、投影和委派的确定性工程证据。
测试使用受控同步替身及 MockTransport；真实模型的业务判断、工具选择质量、委派收益和
恢复节省仍需另行授权的真实输出与独立 oracle。没有据离线通过关闭这些语义验收。

写入、项目决定与前缀回放保持关闭，后续按各自任务实施。本轮交付为一个本地聚焦提交，
不推送、不发布、不读取凭据，也不运行旧评测或 Holdout。
