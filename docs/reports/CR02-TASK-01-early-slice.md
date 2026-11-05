# CR02 TASK-01 早期六例材料结果

日期：2026-10-30。早期切片已准备，TASK-01 全量公开材料仍有后续项。
六例是 CR02-F01/F02/C01/C03/H01/H02，未新增业务 case/trial 身份。

交付 `benchmarks/contract_review/`：10 份实际正文、六例输入、独立 oracle、
两条人工脚本、保留原 24 case 的选择清单。H01/H02 的初始请求和 sources 相同，
仅在问题出现后分别确认 v1/v2。模型授权、profile 和批次预算保持空缺。

验证：`uv run --no-project --offline python -B -m pytest -q
tests/contract_review/test_public_fixtures.py -p no:cacheprovider`（首次命令额外
包含无效但无副作用的 --no-sync；uv 明确提示，后续省略）。实际 9 passed，
0.06 秒；Ruff check/format --check 对新增 Python 文件通过（7 files）。
设置 PYTHONPATH=产品 src、PYTEST_DISABLE_PLUGIN_AUTOLOAD=1、
PYTHONDONTWRITEBYTECODE=1，使用现有 Python 3.12.10，没有创建 venv 或同步依赖。
这是材料闭合与隔离验证，不是产品链测试或语义通过，全部 AC 保持 NOT_RUN。

## 来源与迁移登记

原资产索引沿已读交接文件
`D:/Downloads/agent学习/AI_HANDOFF/2026-10-29-GPT讨论交接/V0_2_TEST_ASSET_MAPPING_2026-10-30.md`。
本轮未重新读取原六轨，保留其历史结果。下表是已完成材料准备的适配来源，
旧包目录版本为 eval-suite-20261026，精确旧运行 SHA 未由本轮核实。

| 迁移行 | 原始 case/check 来源 | 本次适配 | 新证据 |
| --- | --- | --- | --- |
| M19 | COV-07/13/16；G1-G01/G02；`D:/Documents/spec agent/outputs/eval-suite-20261026/outcomes/cases.json` | F01/F02/C01/C03 新业务材料，静态判断与运行实测分开 | 材料已准备；真实输出/人工 oracle 仍 NOT_RUN |
| M05 | COV-17/23/30；G2-009、G3-002/008；旧包 `retrieval-evidence/cases.json`、`process-stability/cases.json` | H01/H02 相同初始来源、不同 review-local 答案；实际请求消费待 TASK-05 | 初始隔离测试通过；答案消费与语义仍 NOT_RUN |
| M02 | COV-06；G1-C03/C05/C06；旧包 `outcomes/cases.json` | 固定 CR02/TR02/SP02 身份、材料检查与语义状态分离 | manifest 身份检查通过；完整评价归属待 TASK-09 |

其他 M01—M24 仍沿原映射逐任务实施，不假称本次已迁移其代码或重新验证其 PASS。
TASK-02 可使用此六例切片；其余 COMMON 材料需在全量验收前补齐。
