# TASK-04 前置审查与修复

日期：2026-10-31。用户要求使用 Stop That Shit，开一个只读子代理审查此前代码。
子代理固定审查 28aba3d，相对 afcc2d7 检查 TASK-02/03 已实现范围；未将未来功能算作缺陷。

## 审查结论与处理

| 严重度 | 固定提交中的问题 | 本次修复 |
| --- | --- | --- |
| P1 | sources.py:148 仅校验 git-dir/common-dir；objects/info/alternates 可指向允许根外的对象库并返回其正文 | 读取 commit/blob 前校验解析后的对象库及 info 目录，并明确拒绝当前不支持的 alternates；info 目录本身可不存在 |
| P2 | worker.py:118 的 I/O Thread.start 异常只被外层捕获，worker 退出后 job/review 留在 running，无错误终态 | 用启动门禁阻止未获放行的 wrapper 进入 adapter；启动/派发准备失败时撤销门禁、确认线程退出并持久化失败；已证明未进入的调用原子释放槽及未执行预留 |

两项均由子代理在固定提交的临时源码副本中离线复现。主代理增加回归测试后，
确认修复前失败，随后实现修复。模型物理请求计数与逻辑 step 序号分开，
已证明未执行的预留退款不会复用旧 step 序号；退款按 call/执行实例去重。

## 验证

新增四项参数化测试实例：外部 alternates 拒绝、普通仓库缺少可选 info 目录仍可读、
线程原生启动失败、线程部分启动后抛错。后两项验证 adapter 零调用、失败终态、
预留释放不重复，以及下一项队列继续执行。已有超时/迟到/UNKNOWN 场景继续通过。

- contract_review 模块：116 passed，115.59 秒。
- 全量离线：**1228 passed、3 skipped、2 warnings，169.83 秒**。
- 全库 Ruff check、format --check（253 文件）和 git diff --check 通过。

沿此前已验证的离线测试方法：当前 src＋本轮临时构建 wheel 元数据，禁用外部 pytest
插件与 bytecode，仅在子进程清除 Provider 配置，HTTP 由 conftest 阻断。
全量日志：`C:/Users/50469/AppData/Local/Temp/specflow-cr04-precheck-pytest-20261031.log`。
没有真实模型、旧评测或实际产品数据库调用；没有推送或发布。

本记录关闭这两项可复现缺陷，不代表完整安全审计。TASK-04 的动态取证、一级委派和
Provider 适配仍按 `docs/tasks/CR02-TASK-04.md` 继续；本次未实现这些新增能力。
