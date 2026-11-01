# TASK-05 Astra 独立审查与修复

日期：2026-11-01（Asia/Shanghai）。审查固定范围：`e20d707` → `6271998`。
状态：两项缺陷已修复，Astra 限定复核与最终全量门禁通过，本地聚焦提交交付。

用户指定审查子代理使用 **gpt-6-astra / xhigh**。此前 TASK-05 子代理负责测试，未显式
指定该模型；本次为单个独立只读审查者。只审 TASK-05，不扩展到后续任务或全项目审计。

## 已确认并修复的两项 P2

| 问题 | 已复现行为 | 修复 |
| --- | --- | --- |
| 未声明的 profile 漂移 | 同名注册 profile 的 prompt 改变后，只提交原样 request 的 revision 仍返回 202 并冻结新配置 | 未提供 execution_profile_id 时必须与原冻结配置一致，否则 409 RETRY_PROFILE_UNAVAILABLE；显式选择仍允许采用新配置 |
| 不足处理误伤同目标的独立工作 | 同目标包含兼容性缺证与独立拼写检查；只对兼容性 mark_insufficient，下一报告却因拼写 work=ready 被拒，最终 ACTION_PROTOCOL_ERROR | 答案保存宿主 check_ids；按稳定检查项映射当前 finding/work，仅限制相关工作和检查缺口，不把整个 target 降级 |

finding/work 的 ID 只在各自报告内有效。检查项关联在宿主接受答案时从原问题的 finding/
work 关联和 check_results 形成，后续不依赖模型复用局部 ID。新回归同时验证局部 finding
ID 改名后，独立工作仍可 ready、相关工作仍被约束。无需新 schema 或依赖。

## 证据

- Astra 原始反例：2 failed，5.32 秒；错误均为正确预期与实际行为不符。
- 父侧修复后原反例：2 passed，4.16 秒。
- Astra 限定复核独立运行同脚本：**2 passed，4.85 秒，退出码 0**，原两项 finding 已闭合。
- 原检查点 54 项与新增配置回归 3 项通过；新增关联正反例在补正测试 URL 导入后
  **2 passed / 3 deselected，4.75 秒**。最终全量会统一重跑全部测试。
- 新增 `tests/contract_review/test_checkpoint_review_fixes.py` 共 5 个场景，覆盖配置继承/
  显式采用、独立工作、相关工作及局部 ID 改名。全库 Ruff check/format --check 通过（269 文件）。

原始 TEMP 脚本：
`C:/Users/50469/AppData/Local/Temp/task05-astra-review-repro-20261101.py`。
最终新增回归已纳入仓库，复查不依赖 TEMP 脚本。

最终全量日志：
`C:/Users/50469/AppData/Local/Temp/specflow-cr05-astra-fixed-pytest-20261101-retry.log`。
首次全量为 1393 passed / 1 failed / 3 skipped，433.61 秒。唯一失败是既有
`test_scheduler.py::test_deadline_waits_for_started_work_before_returning` 的 20ms 启动时序
断言；该模块随后定向 **15 passed，0.74 秒**。没有修改调度器或该旧测试，保持相同代码
重新执行完整门禁。首轮日志保留为同目录下去掉 `-retry` 的日志名。
最终重跑 **1394 passed / 3 skipped / 2 warnings，353.91 秒**，其中 contract_review
**282 项全部通过**，旧调度器时序用例也通过。跳过和警告均为原有条件，无新增 skip/xfail。
全库 Ruff check、format --check（269 文件）、git diff --check 与离线 wheel 均通过。
离线 wheel：
`C:/Users/50469/AppData/Local/Temp/specflow-cr05-astra-fixed-build-20261101/specflow_agent-1.1.1-py3-none-any.whl`。

沿既有 Python 3.12.10、uv no-project offline、src 优先与本轮 wheel 元数据方法；关闭外部
pytest 插件和 bytecode，按名称移除四项 Provider 环境配置，conftest 阻断真实 HTTP。
没有真实模型业务调用、推送或发布。审查/修复不等于已取得真实业务语义验收。
