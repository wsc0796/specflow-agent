# CR02 TASK-02：受控执行纵向切片

日期：2026-10-30。状态：纵向切片已实现；完整产品及 TASK-02 总验收未关闭。
本轮按已选 A/A/B/A/A 和 Stop That Shit 的 change 模式实施。

已接通认证 POST 受理、固定 Git 快照、持久排队、单 worker、分析/固定复核、
正式报告保存与 GET 查询。运行 adapter 限显式注入的 `execution_mode=test`；
默认应用不选择 Provider。测试报告明确记录 test，业务语义验收仍为 NOT_RUN。

主要实现位于 `src/specflow/contract_review/`，主入口修改限 `src/specflow/main.py`。
新数据使用独立表、有 checksum 的迁移和一致性备份；没有修改旧 Run/Provider 语义。

## 已取得的工程证据

- 原始提交与规范化输入分别保存；目标和 checks 由宿主绑定，未知字段/重复项拒绝。
- Git 原始 blob 字节密封，禁替换/隐式取回；脏工作树不影响输入；不支持来源明确拒绝。
- 创建、容量、输入/job、事件及幂等成功响应同事务；失败不留下半成资源。
- OS 实例锁、数据库活动 job 唯一约束、claim 和 owner/token/input/deadline fencing。
- 模型请求完整投影及意图先提交再派发，计数、用量预留、实际用量和本地槽分别维护。
- 超时保留槽；确认线程退出后维护结算、继续 queued。迟到正文不成为正式结果，
  旧重复信号不能释放下一调用的槽；部分用量、bool、冲突值与重复结算有对应测试。
- 报告集合、类型化引用、实际入模片段、任务依赖及 quality 确定性校验；固定复核最多
  一轮返工。结构拒绝保留 rejected 结果，不写合格报告。
- 新 revision 的内部入队事务清空 current_report，保留累计账和历史报告；失败整批回滚。
  revision 的公开 API 与人工答案消费仍按后续 TASK-05 接入。

## 验证结果

最新聚焦命令：

```powershell
uv run --no-project --offline python -B -X utf8 -m pytest -q tests/contract_review tests/test_runs.py tests/test_api_security.py -p no:cacheprovider
```

实际 105 passed、1 skipped，67.45 秒。跳过为已有 Windows 符号链接权限条件。
PYTHONPATH 固定为本 checkout/src；关闭外部 pytest 插件和 bytecode；仅在测试子进程
按名称删除 Provider 环境变量，不读取值。现有 conftest 阻断真实 HTTP。
新 worker 用受控同步替身，未运行真实模型或旧评测。

全库 Ruff check、format --check 通过，250 个 Python 文件；git diff --check 通过。
主入口接线后的最终全量 pytest：**1169 passed、3 skipped、2 warnings，127.43 秒**。
三个跳过均为已有 Windows 符号链接权限条件；两个警告为已有 TestStrategy 类收集提示。

前一轮全量结果为 1141 passed / 3 failed / 3 skipped：两项 CLI 配置缺失测试
在隔离环境后定向通过；剩余发布元数据检查读到本机已安装包 0.1.0，而源码为 1.1.1。
相关旧源码与测试相对起点无修改。

使用已有声明的构建配置运行 `uv build --wheel --offline --out-dir <临时目录>` 成功。
构建产物为 `C:/Users/50469/AppData/Local/Temp/specflow-cr02-build-20261030/specflow_agent-1.1.1-py3-none-any.whl`。
最终测试的 PYTHONPATH 顺序为当前 checkout/src、该 wheel；实际核对源码仍来自
当前 src，importlib.metadata 来自本轮真实构建的 1.1.1.dist-info。没有修改全局
安装包、依赖声明或版本断言。版本相关定向测试 5 passed 后，全量复测得到上述通过结果。
最终日志：`C:/Users/50469/AppData/Local/Temp/specflow-cr02-final-pytest-20261030.log`。

## 剩余边界

动态五工具和真实 HTTP adapter、完整外部核验、人工答案/公开 revision/fresh API、
薄 CLI 及其语义验收尚未交付。当前受控链把有限快照正文完整投影，超出冻结上下文
上限即失败；TASK-04 才接动态取证。该切片不能据此宣称方案 1 已全部完成。
所有正式 AC 需沿原验收矩阵逐项关闭；已有工程结果不升级为语义 PASS。
