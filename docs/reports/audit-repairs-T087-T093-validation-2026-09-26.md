# T-087–T-093 修复方案与验证报告

- 日期：2026-09-26；状态：七项修复完成，独立审查通过。
- 仓库：`D:\Documents\ChatGPT\一个月冲刺\specflow-agent`。
- 分支：`codex/t087-t093-audit-repairs`；基点：`5a9000a6a20cea42cbb1b38e90f937810e1a3014`。
- 用户授权：在七项只读审查发现后确认“可以修复”。继续在保存的 checkout 工作，本地提交，不推送。
- 使用 adaptive-sdd、project-testing-engineer、TDD、verification-before-completion 与 requesting-code-review。

## 修复方案

| 项目 | 最终行为 | 提交 |
|---|---|---|
| [T-087](../tasks/T-087-revision-request-delivery.md) 修订请求 | 目标 Agent 收到修订指令、已接受 Review 输出和自己的旧输出；完整计入输入预算；其他接收者保持隔离 | 6561c81 |
| [T-088](../tasks/T-088-semantic-brief-delivery.md) 任务说明 | 每个 Agent 收到自身 brief 的四个语义字段，修订时复用；正常及 degraded brief 均有效 | 108e340 |
| T-087/T-088 审查补修 | 先逐字符串值脱敏再序列化；敏感值不会破坏 JSON 或删除后置字段 | 52f3ed1 |
| [T-089](../tasks/T-089-artifact-integrity-coverage.md) 完整性 | 要求固定七个数据文件的完整哈希集合；拒绝空表、漏项、额外路径、非法哈希与链接；不读取表中任意路径 | 77215f8 |
| [T-090](../tasks/T-090-usage-observation-contract.md) 用量口径 | 新 manifest 声明 all_provider_requests_v1，交叉验证 budget_usage 与 metrics；有观察记录才拆分 Agent/Coordinator；旧契约保留原义 | b4b0893 |
| [T-091](../tasks/T-091-evidence-tool-failure-artifacts.md) 证据失败 | list_files 失败显式停止；collection/setup 异常均写安全失败 manifest，保留实际工具次数及受控错误类型；deadline 优先 | 7264cf3 |
| [T-092](../tasks/T-092-artifact-import-shapes.md) 导入形状 | JSON null、错误容器及不可哈希成员返回 FAILED/findings；不再崩溃或误通过 | 8d0669d |
| [T-093](../tasks/T-093-deterministic-cancellation-tests.md) 测试同步 | 三处 Timer 改为状态同步；确认 worker/Future 状态后超时，完成全部取消观察后释放；主线程暂停场景与 finally 清理覆盖 | 与本报告同一提交 |

修订块与 brief 仍受既有输入 Token 准入、响应 usage 核算和单轮修订边界控制。未提高默认额度、添加依赖或修改调度器生产代码。

## 验证证据

外部原始证据目录：
`D:\Documents\ChatGPT\一个月冲刺\specflow-repair-backups\2026-09-26-T087-T093`。

| 项目 | RED | GREEN |
|---|---|---|
| T-087 | 4 failed：三个目标未收到修订、超限仍调用 | 85 passed |
| T-088 | 3 failed：正常/degraded brief 未交付、大 brief 未拒绝 | 79 passed |
| T-089 | 5 failed / 3 passed：覆盖缺口及非法路径反例 | 29 passed |
| T-090 | 4 failed / 24 passed：无新契约及全调用字段 | 75 passed |
| T-091 | 4 failed：缺少失败 manifest | 第二轮 84 passed / 1 skipped / 1 warning |
| DLP 审查补修 | 2 failed / 7 passed：后置字段丢失且 JSON 不可解析 | 28 passed |
| T-092 | 17 failed / 6 passed：错误结构异常或误通过 | 48 passed |
| T-093 | 独立重放三个旧测试均 DID NOT RAISE | 52 related passed；10 个独立进程各 11 passed |

最终全量命令（仓库根目录）：

```powershell
uv run --offline --no-sync python -B -X utf8 'D:\Documents\ChatGPT\一个月冲刺\specflow-repair-backups\2026-09-26-T087-T093\validate.py' audit-repairs-full -v
uv run --offline --no-sync ruff check .
uv run --offline --no-sync ruff format --check .
```

- **974 passed、3 skipped、3 warnings，99.10 秒，exit=0**，比基点新增 75 个测试案例（含参数化场景）。
- 原始日志：[audit-repairs-full.log](../../../specflow-repair-backups/2026-09-26-T087-T093/audit-repairs-full.log)。
- 隔离记录：[audit-repairs-full-isolation.json](../../../specflow-repair-backups/2026-09-26-T087-T093/audit-repairs-full-isolation.json)。
- Ruff lint 通过，format 检查 231 个文件通过；diff 检查通过。
- 3 个 skip 是 Windows 符号链接权限限制；3 个 warning 为既有 TestStrategy 类收集和 FastAPI/httpx 弃用警告，没有新增 skip/xfail。
- 包装在导入前清除 SPECFLOW_LLM_*，阻断主/子进程真实 HTTPTransport；全量含 1 个临时 Mock worker、246 次净化子进程启动，主/子 HTTP 均为 0。该包装不是操作系统网络沙箱。
- 七份规格通过 plan/verify 结构与追溯检查。各项报告保留对应日志名称。

T-091 首轮相关回归有一项失败：原 CapturingCollector 测试替身缺少实际 Collector 的 tool_call_records 接口。补齐空记录属性后通过，原断言未变。独立审查发现的 JSON 脱敏问题已先复现再修复，未隐藏失败记录。

## 独立审查

审查者按 requesting-code-review 对源码、实际调用链及回归边界独立核对。首轮发现 1 个 Important（整段 JSON 脱敏），修复后以原合成反例复查：两个数据块仍是合法 JSON，后置字段完整。最终七项范围审查无 Critical、Important 或 Minor。审查者没有代替主窗口执行最终全量。

## 边界与保留事项

原 17 份 dirty 学习文档/Word 已定向备份并逐文件比对，内容不变；CURRENT、learner PARTIAL、原 Day14 事件与历史产物均保留。未修改 benchmarks/data/datasets，未读取或运行正式 Dev/Holdout、未调用真实 Provider。新增产物的用量契约不会重写历史报告。

本批证明请求交付、预算、失败分类、Artifact 校验及测试同步，真实模型修订质量仍需独立授权的效果评估。哈希覆盖校验不等于真实性认证；同步线程无法强制中止的既有边界不变。测试中的等待上限仅用于失败时退出，任务释放由状态事件决定。

每项可用对应本地提交回退；DLP 补修依赖 T-087/T-088。没有推送、发布或创建 PR。
