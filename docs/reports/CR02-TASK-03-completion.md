# CR02 TASK-03：规则与外部核验闭环

日期：2026-10-30。基线：3803f5a；范围：A/A/B/A/A。

新增认证接口：POST `/api/v1/contract-reviews/{id}/verification-evidence`，以及同路径的
GET 列表和 `/{evidence_id}` 详情。有效的提供者记录以 201 保存为
`provided_not_independently_verified`；不触发作业，不改写原报告的 NOT_RUN。

导入先重放已成功的同键同请求，再核对资源归属、expected_version、当前 input/report
和源码 commit。三类 409 分别为 VERSION_CONFLICT、VERIFICATION_TARGET_NOT_CURRENT、
VERIFICATION_BASELINE_MISMATCH；非法提交不留下记录或推进版本。

内部 revision 接点支持显式选择、继承已有选择和显式清空。每次采用都会冻结独立绑定，
按源码、同一目标、规则用途和检查选择器重新判断 applicable/inapplicable/unresolved。
新导入记录不会自动混入继承集合；原证据归属始终保留。GET 展示原归属、当前采用和
逐目标适用性，查询本身不改数据。选入正文进入实际请求投影；过大时明确失败。

规则采用增加历史/越界原因区分。报告校验补齐规则差集未知传播、规则原文完整性、
外部证据逐目标支持与实际入模检查；动作理由及固定复核的问题对象/引用也校验归属。
正式报告带冻结规则原文、采用用途及外部证据声明摘要，仍由固定复核判断业务语义。

## 迁移与测试

schema v2 只增加核验表和索引，保留 v1 checksum
`90c77e6473bdf6bd2d0b2526199421fe2391e8a4dfefee5f6650b2328f48f061`。
临时副本测试覆盖 v1 带排队输入升级、升级前一致性备份、重入、失败整体回滚和旧数据读取。

`tests/contract_review/` 最新结果：**112 passed，76.43 秒**。覆盖导入 Schema、
弱证保存、冲突顺序、幂等、并发 CAS、跨审查拒绝、分页、权限、存储失败、选择继承、
逐目标适用性、证据送达与上下文超限、报告引用和既有运行链。

全量 pytest：**1224 passed、3 skipped、2 warnings，177.87 秒**。跳过均为已有 Windows
符号链接权限条件；两个警告为已有 TestStrategy 类收集提示。
全库 Ruff check、format --check 通过（253 个 Python 文件）；git diff --check 通过。
测试沿既有离线方法：当前 src 为首个 PYTHONPATH，临时离线构建 wheel 提供同版元数据；
关闭外部 pytest 插件/bytecode，在测试子进程按名称清除 Provider 配置，现有 conftest 阻断 HTTP。
没有改依赖声明、全局安装或旧测试预期。

构建产物：`C:/Users/50469/AppData/Local/Temp/specflow-cr03-build-20261030/specflow_agent-1.1.1-py3-none-any.whl`。
全量日志：`C:/Users/50469/AppData/Local/Temp/specflow-cr03-final-pytest-20261030.log`。

## 验收归属和下一步

本轮取得 AC-11/17/23 对应工程边界的新证据；AC-01—06 等模型业务判断仍须真实输出和
独立 oracle，未据程序测试提升为语义 PASS。动态快照工具及真实 adapter 接入留在 TASK-04，
人工答案与公开 revisions 留在 TASK-05。没有运行真实模型、推送或发布。
