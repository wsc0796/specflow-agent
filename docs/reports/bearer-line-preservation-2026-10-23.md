# Bearer 脱敏行号保持修复结果

日期：2026-10-23。任务：[限定范围与验收](../tasks/bearer-line-preservation-2026-10-23.md)。
基线：`773cab9e24bdcf4f990afe7897dcdf7459c4e372`。
审查分支：`codex/bearer-line-preservation`，基于 `fix/provider-failure-diagnostics`。

**已修复独立 Bearer 识别及凭据分隔符保持。真实案例的读取结果由 32 行恢复为
33 行，搜索位置与读取位置对齐；真实 Bearer 凭据继续隐藏。新增模型调用为 0。**

## 根因与改动

旧正则 `bearer\s+...` 会匹配标识符 `HTTPBearer` 的后缀、换行和下一行的
`from`。工具结果对 content 整串再次脱敏时，固定替换文本吞掉换行。
搜索工具使用原始源码行号，外置原型随后按这些行号索引净化内容，因此发生错位。

修复在共享的 `_BEARER_RE` 中增加单词边界，并捕获原空白分隔符；替换时只
隐藏凭据，保留分隔符。空格、制表符、LF、CRLF 均继续支持，Bearer 大小写
识别不变。最终 DLP、JSON 字符串净化和原有敏感键处理均保留。

仅改动一个生产文件和两个现有测试文件；另外增加任务与本报告。
共享表达式只有一个定义与替换点，三个入口 `sanitize_tool_text`、
`sanitize_json_text`、`final_dlp_scan` 均经过该点。单行元数据入口仍按原设计
折叠控制字符；布局保持验收针对文件内容、JSON 字符串及最终 DLP。
其他 Authorization、access_token 及通用秘密规则没有改变。

## 验证结果

| 检查 | 结果 |
|---|---|
| 新增回归在旧实现上执行 | 12 failed、2 passed |
| 修复后两个聚焦测试文件 | 80 passed、1 个既有 Windows 符号链接跳过 |
| 首次全量检查，继承当前供应商环境配置 | 1067 passed、2 failed、3 skipped |
| 测试进程隔离供应商配置后的全量检查 | 1069 passed、3 skipped、3 warnings，26.05 秒 |
| Ruff check | 通过；保留既有 test_coordinator.py 的 noqa 提示 |
| Ruff format --check | 220 files already formatted |
| 自然案例的只读验证 | 原文与读取结果均 33 行；11 条搜索命中全部对齐 |

首次全量失败的两个既有用例假定供应商配置缺失，但没有自行清除继承的环境：
`test_cli_provider_config_missing_reports_clearly` 和
`test_non_mock_provider_is_rejected_without_executing_agents`。
测试夹具已阻断真实 HTTP；本次仅在测试进程内删除四个供应商配置名后重跑，
没有读取、打印、保存密钥值或改变用户环境，也没有修改这两个无关用例。
失败日志保留，未通过改断言或跳过用例取得通过。

全量检查使用现有 `.venv` 与 `uv run --no-sync python -B`，再调用
`pytest.main(['-v', '-p', 'no:cacheprovider'])`；运行前仅在该 Python 进程内
移除 `SPECFLOW_LLM_API_KEY`、`SPECFLOW_LLM_BASE_URL`、`SPECFLOW_LLM_MODEL`、
`SPECFLOW_LLM_TIMEOUT_SECONDS`。`tests/conftest.py` 的真实 HTTP 阻断保持启用。

## 真实源码的局部回归

对只读目标 `sky-takeout-python` 的 `app/api/dependencies.py` 进行一次
read_file 和一次 search_code，检查原第 21、27、29、33 行，以及全部 11 条
搜索命中。修复后位置一致，最终 DLP 不再改变这些行的位置。
目标保持 `4ede5d01039be8c703e4cc2cc94f18084ebf1ba1`，未修改任何文件。

没有重跑整个取证原型、下游 Agent 或真实模型。原先的 6/8 覆盖、配置类遗漏、
Redis 未入选和证据体积问题仍是原试次结论，不能用本次局部回归改写。

## 评测结论和交付边界

本次直接验证用户八维框架中的“证据”和“安全与权限”：源码引用位置保持，
真实凭据格式继续脱敏。LF/CRLF 和嵌套结构是确定性回归，不代表模型稳定性。
RAG 完整性、Agent 规划/路由、故障恢复、业务端到端结果及模型成本收益未在本单元
重新评测；没有增加记忆功能或把这些方向登记为完成。

设计、实现与测试由 Codex 协作完成；用户选择并批准限定修复。
不自动登记为用户已独立掌握，也不生成未经验收的简历收益数字。

本修复按依赖分支建立草稿审查，尚未合并。现有 CI 仅监听 main 为目标的 PR
及 main/tag push，本依赖分支草稿不应被描述为远端 CI 已通过；本报告的验证依据
是上述本地离线结果。长期 Goal 未完成。
