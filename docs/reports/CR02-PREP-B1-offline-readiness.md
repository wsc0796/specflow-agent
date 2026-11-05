# CR02 PREP-B1：F02、H01/H02 离线链路

日期：2026-11-04（Asia/Shanghai）。状态：首批B1离线工程交付完成，最终全库门禁通过；真实业务语义NOT_RUN。

用户已明确按 v0.2 启动首批 B1，仅新增约定的两个脚本、两个测试和本报告。
任务合同：[v0.2 首批B1范围](D:/Downloads/agent学习/AI_HANDOFF/2026-11-04-离线准备任务单-v0.2/SPEC_FLOW_OFFLINE_EXECUTION_PREP_v0.2.md)。
产品基线：`99a8baa0c2de38751a6ccce48d8b97e85ad1ec90`。
已有 `AGENTS.md` 与 `docs/reports/CR02-CURRENT.md` 修改保留。

目标：复用固定公开材料和现有 API，验证 F02 受理／报告采集及 H01/H02
合法问题、原文答案、自动派生和历史证据。默认 CLI 仅准备；工作流只接受注入的进程内测试环境。
不修改 src、F01／guard、原案例／判据；不运行真实模型、读取凭据、提交或推送。

验证矩阵：固定身份／材料、准备零外发、F02 报告、H 动态问题与 200/202、
原文入父分析／复核、错误停止、分页／旧报告／新 job、版本与采用分离、未知／失败分类。
新增工作流使用 contract-review-engine.v2，固定 profile 为 b1-offline-public-v2，
write/project_memory/delegate/replay 均关闭。真实业务语义保持 NOT_RUN。

## 当前实现与已取得结果

- run_public_case_prep.py：固定 F02/H01/H02 和原材料身份；默认 CLI 仅准备，
  不导入或启动产品运行底座。显式工作流只接受已注册 test profile／受控 adapter 的进程内 TestClient。
- review_evidence.py：逐 job 分页取完整事件与请求正文，保存每轮状态／输入身份和历史报告。
  规则版本视图与逐目标采用分开；正文／历史／版本缺失均留缺口，不请求完整历史输入 API。
- 两个测试文件：13 项约定行为映射为32个参数化节点，覆盖实际 API／worker／问题／答案／派生链，
  以及采集层的缺证反例；替身仅在测试内生成受控报告。
- 准备命令无 --run 入口；拒绝外部 HTTP client、live 配置、错 case/sample/trial、
  改写后的请求或 source grants；不放宽既有 F01 与 guard。

已有执行（不得相加冒充一次全库）：

| 运行 | 实际结果 | 说明 |
| --- | --- | --- |
| 初次新增两模块 | 26 passed / 4 failed / 1 warning，26.55s | 两项 job 完整性、错版本漏检和环境测试替身问题；原失败保留 |
| 六模块候选回归 | 200 passed / 1 failed / 1 warning，158.70s | 唯一失败为测试替身误拦标准库 COLUMNS，不是读取认证；旧模块通过 |
| 修复后新增两模块 | 31 passed / 1 warning，27.05s | 含完整 F02/H01/H02 v2 链路；之后补充一项损坏请求正文反例 |
| 最终采集模块 | 15 passed / 1 warning，0.24s | 包括上述新增正文损坏边界 |
| 全库 Ruff | check通过；format --check 300 files already formatted | 全库 pytest 前冻结代码，报告可继续更新 |
| 最终完整全库 | 1715 passed / 3 skipped / 3 warnings，624.53s，exit 0 | 收集1718项，包含全部32个B1新增节点；同次运行的三例JSON与完整日志已归档 |

初次日志：C:/Users/50469/AppData/Local/Temp/specflow-b1-first-e65d6b4475084b4e8166f3bc55f26da1.log。
六模块候选日志：C:/Users/50469/AppData/Local/Temp/specflow-b1-focused-cb3a25ae23974803ac93c9e2604ef8be.log。

## 最终门禁与复查入口

最终运行目录：C:/Users/50469/AppData/Local/Temp/specflow-b1-final-e7d19a49d3944c39ab3b218c680bd080；pytest-full.log保存完整输出，
source-snapshot.json固定四个代码／测试文件的字节指纹；pytest产物在其pytest/下。
命令：uv run --offline --no-sync pytest -v -s --tb=short -p no:cacheprovider --basetemp=<该目录>/pytest。
实际收集1718项：1715 passed / 3 skipped / 3 warnings，624.53秒（10:24），退出码0。
三项skip均为已有Windows符号链接权限条件；三项warning为已有Starlette/httpx弃用和两个TestStrategy类收集提示。

测试进程关闭bytecode／外部pytest插件，按名称移除真实Provider和服务认证变量，不读取／回显值。
现有conftest阻断真实HTTP，本批工作流显式注入假认证和受控adapter；未发送真实业务模型请求。

已核对原始总结、退出码和32个新增节点；同次运行的F02/H01/H02 JSON及完整日志已归档。
四个代码／测试文件与开跑时字节指纹一致，src/F01/原案例无差异，两个既有用户修改保持原差异。
未授权提交或推送；不扩展记忆A/B/C、候选记忆材料、真实试验、E03/AC-10或完整TASK-09。

## 实际离线输入、动作与输出

F02：准备原有四来源和两个目标 → API受理 → v2分析／固定复核 → 正式降级报告。
H01/H02：相同初始业务材料 → 正式scope_choice问题 → 读取宿主问题ID → 提交各自原答案 →
宿主返回202并自动派生input/job → 新分析／固定复核 → 新报告；旧报告按ID读回且保持原文。

| 案例 | 输入／job／报告数 | 请求投影数 | 答案结果 | 业务语义 |
| --- | --- | --- | --- | --- |
| [F02](D:/Downloads/agent学习/AI_HANDOFF/2026-11-04-B1-离线验证产物/CR02-F02.json) | 1 / 1 / 1 | 2 | 不提交人工答案 | NOT_RUN |
| [H01](D:/Downloads/agent学习/AI_HANDOFF/2026-11-04-B1-离线验证产物/CR02-H01.json) | 2 / 2 / 2 | 4 | 原文“属于API v1”，202自动派生 | NOT_RUN |
| [H02](D:/Downloads/agent学习/AI_HANDOFF/2026-11-04-B1-离线验证产物/CR02-H02.json) | 2 / 2 / 2 | 4 | 原文“属于API v2”，202自动派生 | NOT_RUN |

三例最终均为completed_degraded，collection_complete=true；受控替身报告明确不提供真实业务判断。
H两例后继报告回显各自原答案，只用于观测传递链，不据此签发v1/v2业务结论。
部分回答200／最后202／同键成功重放的独立测试确认唯一后继job，未请求额外revisions。

同次最终全库的JSON已逐字节复制到：D:/Downloads/agent学习/AI_HANDOFF/2026-11-04-B1-离线验证产物。
文件为CR02-F02.json、CR02-H01.json、CR02-H02.json；evidence-index.json记录原始来源与最终PASS，
pytest-final-full.log为原始完整日志，pytest-b1-node-excerpt.log逐行标出同次运行的32个新增节点。
[证据索引](D:/Downloads/agent学习/AI_HANDOFF/2026-11-04-B1-离线验证产物/evidence-index.json)；[最终原始日志](D:/Downloads/agent学习/AI_HANDOFF/2026-11-04-B1-离线验证产物/pytest-final-full.log)。

另做一次独立的受控调用边界核对，不混成新的业务样本：F02/H01/H02分别捕获2/4/4次adapter.complete输入，
与对应数据库请求投影payload逐条相等。H两例初始请求不含答案，后继父分析和固定复核均收到准确完整答案原文。
真实HTTPTransport／AsyncHTTPTransport被显式阻断并计数，三个场景业务模型HTTP尝试均为0。
原始两组payload保存在各CR02-*-adapter-delivery.json中；它们是进程内adapter调用证据，不是远端HTTP wire或真实模型语义。

边界核对没有改动四个代码／测试文件；全库运行期间其字节指纹保持不变。

## 使用与交付边界

默认准备命令（将输出路径替换为仓库外未存在的新目录）：

    uv run --offline --no-sync python scripts/contract_review/run_public_case_prep.py --case CR02-F02 --output D:/Downloads/b1-f02-new-output

该命令只生成固定材料仓库与preparation.json，状态为PREPARED_NOT_DISPATCHED，不启动审查或Provider。
实际离线工作流通过新测试提供的TestClient／受控adapter执行；run_case、submit_answers及ReviewEvidence
分别承担编排、合法答题与采集，复用现有API和宿主的自动派生。

本轮仅新增两个脚本、两个测试和本报告，无新增依赖，无skip/xfail隐藏失败；未提交或推送。
B1关闭PREP-AC-01的本批版本核对、PREP-AC-02/03的受控工程路径、PREP-AC-08的本批零外发边界及采集契约。
真实模型的无偏离／版本判断、记忆A/B/C、R02/R03/R04/R05/H03材料和oracle、价值对照、
E03/AC-10整体、完整TASK-09和条件写入均不因本次完成而关闭。
