# CR02 TASK-07：可读交付与查询

日期：2026-11-01（Asia/Shanghai）。实现基点：`f77cd7cfddf17883f669b3a669ce990fea5f6947`。
状态：工程实现、指定 Astra 独立审查/修复/限定复核及最终全仓库离线门禁完成。

## 交付行为

`GET /api/v1/contract-reviews/{id}/report` 保持默认 JSON 和原权威正文；增加
`format=markdown` 派生格式。Markdown 展示冻结身份、请求/目标/来源/版本、规则原文与
采用原因、逐检查项及 quality、发现和证据、裁决边界、处理任务/依赖/建议范围、验收方法、
环境及真实执行状态。外部证据的原归属、报告输入采用与逐目标适用性分开展示。
证据定位链接指向该报告/输入/job 的认证入口，另提供当前状态及当前核验采用视图入口。

正文不截尾；不可信 Markdown/HTML/控制字符转义，结构正文采用安全长度的 JSON 围栏。
ready 继续表示信息可交接，execution_authorized 与 NOT_RUN 保留真实值；外部声明和
适用性 null 不升级为系统 PASS 或 false。渲染失败返回可识别错误，原 JSON 与状态不变。

新增认证查询：

- `GET /contract-reviews?project_id=...`：按 (created_at,id) 升序 keyset，每页 1—100；
  游标绑定项目。列表返回 review/input/report/job 身份、版本、状态和失败码。
- `GET /contract-reviews/{id}/questions`：默认仅当前报告；可指定本 review 历史
  report_revision_id，显示原归属、问题完整正文、终局答案和剩余阻塞，不把同名局部问题串联。
- 原状态 GET 增加当前步骤、started/deadline/finished 和最近物理调用的本地/远端/用量状态，
  沿用原 dispatch_gate、累计预算、逐项清单、quality 及当前/历史规则集版本。

事件仍按 review/job 和 event_seq 分页；详情可取得 payload 实际正文。新增只读完整性
投影：正文不可解析、ref/hash 不符、正文超限或元数据不可用时，元数据标为 incomplete，
列出 missing_evidence；详情返回 EVENT_PAYLOAD_NOT_AVAILABLE，不以 hash 充当正文。
GET 不修复、不删写权威记录。

## 薄 HTTP CLI

入口为 `specflow contract-review`，沿用现有 httpx 依赖。一次命令只发一个认证 HTTP
请求，不直读写数据库、不执行导入 procedure、不自动轮询/分页/重试、不跟随重定向。
CLI 运行时从 `--api-key-env` 指定的环境变量取得服务认证，默认 SPECFLOW_API_KEY；
没有明文密钥命令行参数。本轮所有测试只用 CR07_TEST_KEY 等固定假变量。

报告默认 Markdown，其余命令输出 JSON。输入 JSON 文件/标准输入读取上限 1 MiB，
响应上限 8 MiB，超限明确失败；服务端错误保留 HTTP 状态及领域错误码。
`--output` 只新建文件，不覆盖已有文件；HTTP 已成功而输出失败时，提示保留服务端结果，
可查询或用原幂等键重放。退出码：0=收到成功响应并完成输出，2=输入/响应解析/输出失败，
3=HTTP 错误或请求未完成。202 只表示受理，不表示审查或业务核验已完成。

用法（假设已有运行服务及由用户配置的服务认证；以下不含实际凭据）：

```powershell
specflow contract-review --help
specflow contract-review list --project-id project_id --limit 20
specflow contract-review status review_id
specflow contract-review report review_id
specflow contract-review report review_id --format json --report-revision-id report_id
specflow contract-review --output report.md report review_id
specflow contract-review events review_id --job-id job_id --limit 20
specflow contract-review event review_id event_id
specflow contract-review questions review_id
specflow contract-review create --body-file request.json --idempotency-key create-001
specflow contract-review resolve review_id --body-file answers.json --idempotency-key answers-001
specflow contract-review revise review_id --body-file revision.json --idempotency-key revision-001
specflow contract-review import-evidence review_id --body-file evidence.json --idempotency-key evidence-001
specflow contract-review evidence review_id --evidence-id evidence_id
specflow contract-review decisions --project-id project_id --ruleset-version 1
specflow contract-review publish-decision --project-id project_id --body-file decision.json --idempotency-key decision-001
```

POST 文件遵守现有 API Schema，客户端不暗改 expected_version 或幂等键。核验的
VERSION_CONFLICT、VERIFICATION_TARGET_NOT_CURRENT、VERIFICATION_BASELINE_MISMATCH
保持三类拒收；旧成功 key 优先重放。弱证据保留 provided_not_independently_verified；
列表/详情分别呈现不可变 origin、current_adoption、current_applicability 及三值摘要。

## 验证与边界

新增测试：`test_report_queries.py`、`test_review_cli.py`，涵盖真实 TestClient API 与
MockTransport CLI 接线、原 JSON/历史不变、问题答案归属、keyset、认证/参数、正文完整性、
输出失败、核验三类冲突/重放/弱证/原归属与采用、项目决定及真实步骤/gate。

- 旧 intake/迁移接线：19 passed，22.09 秒。
- 新测试修正后：43 passed，66.41 秒。
- 最后受影响/新增场景：11 passed / 34 deselected，15.10 秒。
- 全库 Ruff check/format：277 文件通过；git diff --check 通过。
- 本轮离线 wheel 1.1.1 构建成功，三个新模块已核实打包。
- 审查修复定向：16 passed / 36 deselected，13.01 秒；过深 JSON 单项 1 passed，0.59 秒。
- 指定 Astra / xhigh 独立审查确认三项 P2；修复后限定复核原四条 4 passed，6.26 秒，全部关闭。
- 最终全仓库 pytest：**1513 passed / 3 skipped / 2 warnings，384.69 秒**，退出码0；
  contract_review **401 项全部通过**，包含本轮新增 53 项。

本轮新增为报告/查询 26 项、薄 CLI 27 项。全量统一覆盖原三项 P2 修复后的最终代码。
3 个跳过仍为已有 Windows 符号链接权限条件；2 个警告仍为已有 TestStrategy 类收集提示。
没有新增 skip/xfail，没有修改旧调度器或其他旧流程。最终全量没有失败，无需重复门禁。

三项发现为事件归属元数据不符仍显示完整、覆盖来源引用未进入 Markdown、无效端口异常
逃逸。均已修复并补仓库回归；详情见 `CR02-TASK-07-ASTRA-REVIEW-2026-11-01.md`。
独立代理明确使用 `gpt-6-astra / xhigh / fork_turns=none`，复核只覆盖原发现。

首轮 39 passed / 1 failed / 2 errors 为测试夹具问题：凭据断言误拦 Python 自身环境查询，
以及超大参数用例名触发 Windows 环境变量长度限制；均已修正，首轮日志保留。

日志位于 `C:/Users/50469/AppData/Local/Temp/`：
`specflow-cr07-focused-initial-20261101.log`、`specflow-cr07-focused-fixed-20261101.log`、
`specflow-cr07-last-additions-20261101.log`、`specflow-cr07-review-fixes-fixed-20261101.log`、
`specflow-cr07-final-pytest-20261101.log`。首轮日志含长用例名，读取时应先裁短行。
构建：`specflow-cr07-final-build-20261101/specflow_agent-1.1.1-py3-none-any.whl`。

沿用 Python 3.12.10、uv no-project offline、src 优先与本轮 wheel 元数据；关闭外部
pytest 插件/bytecode，测试子进程按名称移除四项 Provider 配置，既有 conftest 阻断真实
HTTP。没有迁移、依赖、框架或全局安装改动。

复查命令（在产品目录执行）：

```powershell
$wheel = Join-Path $env:TEMP 'specflow-cr07-final-build-20261101\specflow_agent-1.1.1-py3-none-any.whl'
uv build --wheel --offline --out-dir (Split-Path -Parent $wheel)
$env:PYTHONPATH = (Join-Path (Get-Location) 'src') + [IO.Path]::PathSeparator + $wheel
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
uv run --no-project --offline python -B -X utf8 -c 'import os,pytest; [os.environ.pop("SPECFLOW_LLM_"+name,None) for name in ("API_KEY","BASE_URL","MODEL","TIMEOUT_SECONDS")]; raise SystemExit(pytest.main(["-v","--tb=short","-p","no:cacheprovider"]))'
uv run --no-project --offline ruff check .
uv run --no-project --offline ruff format --check .
```

仅交付 TASK-07，本轮代码、测试与报告一同本地聚焦提交；不调用真实模型业务通道、不读取凭据/Holdout、
不推送发布。写入、retry 新入口、前缀回放、旧 runner 旁支和完整业务语义验收仍按后续任务。
