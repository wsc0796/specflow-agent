# H04/F03 独立审查收尾

日期：2026-10-24；基线7fd7f2f；任务见[限定范围](../tasks/offline-review-closeout-2026-10-24.md)。

后续补记：本文保留9586db1时的验收记录。两项旧provider-resilience INFO断言已在[后续收尾](./info-logging-scope-and-h04-plan-2026-10-24.md)按自有输出/第三方日志边界修正，WARNING/INFO均覆盖；新全量1112 passed。旧压缩包及本页历史数字未替换。

本次修改测试和证据表述，不修改生产代码。模型调用0次。

## 已复现的问题与处理

1. **INFO日志口径。** 原两个F03工作流用例开启INFO均失败，失败内容是HTTPX记录的配置端点；不是异常正文或Authorization进入manifest。本次分开配置端点和异常正文的URL标记，显式启用INFO：异常正文、合成凭据不得进入观测输出；配置端点不得进入自有诊断/原生产物，不对第三方日志作普遍隐藏保证。
2. **生产调用包装。** 两份测试不再替换_create_real_llm_client，改在Provider构造边界注入MockTransport和独立熔断状态，保留timeout cap及实际attempt_executor。测试检查截断后的timeout和执行通道调用次数。
3. **反馈对象。** 保留原长文本/隔离断言，并解析实际请求中的反馈JSON，完整比较target_agent_id、round_number、summary、findings。
4. **晚阶段故障。** 新增16个变体，覆盖专家、综合、评审及返工/重综合/复审。与原Analyst两变体合计两类故障×九个位置=18个工作流检查。成功并行同级可结束，但失败产物不得下传；manifest及run/coordinator trace准确保留故障角色/阶段。
5. **审查材料。** 打包范围补入既有tests/fixtures/required-output-validity.json，并从全新解压目录执行收集和全部附带测试。结果记录在用户验收包中，不能将附带子集计数冒充产品全量。

## 验证

| 检查 | 结果 |
|---|---|
| 原测试INFO反例 | 2 failed / 8 deselected，日志保留 |
| 初步接线与范围纠正 | 原25项全部通过 |
| 新的晚阶段探针首次运行 | 16失败均来自新测试误用所有span均有kind字段；产品前置诊断断言通过 |
| 探针修正 | 只选择run/coordinator span并断言恰好两个，保持全部诊断/下游断言；随全量全部通过 |
| 产品全量离线 | 1110 passed、3既有skipped、3既有warnings，30.38秒 |
| Ruff check / format --check | 通过，222 files already formatted |
| 新增真实模型调用 | 0 |
| 全新解压目录收集与执行 | 补齐JSON夹具及其导入的test_runs.py；308 passed、1既有skipped、2 warnings，12.50秒 |

测试误写KeyError记录属于测试代码问题，不当作新的产品缺陷。原25项、后续16项以及不同聚焦组不能重复相加。
三项跳过为Windows符号链接权限，警告为既有测试类收集和TestClient依赖弃用；未增加skip/xfail。

第一次材料验证的失败同样保留：仅补JSON后收集成功，但执行时还缺test_runs模块；额外给整套旧测试开启全局INFO，还触发test_provider_resilience.py中两项既有的配置端点断言。后者不是本次修改引入的问题，本单元没有扩大修改旧测试或日志系统。最终包按产品默认测试口径运行；F03自己的测试仍显式开启INFO。不得把该通过结果写成“全局任意日志级别全部通过”。

## 运行口径

使用现有依赖和uv --no-sync，测试进程隔离继承供应商配置，不读取/打印其值。既有全局真实HTTP阻断保留。实际导入路径核验为当前工作区。

日志目录：D:\Documents\spec agent\outputs\goal-offline-reliability-20261024。
关键文件：info-scope-red.log、review-closeout-focused.log、review-closeout-all-positions.log、pytest-full.log、ruff-check.log、ruff-format.log。

## 可支持与不可支持

可以支持：真实工厂/执行通道下的离线反馈送达；ReadTimeout/503在所测九个位置的终端诊断、未知用量和下游阻断；明确的日志边界。
不能支持：真实模型纠错提升、真实供应商自动恢复、所有日志无端点、所有故障覆盖、完整尝试账本。

本次用户明确授权离线Goal；代码、测试和文档由Codex协作完成，不自动认证用户独立掌握。
同一Goal的compact修改是独立外置原型，未并入生产，不包含在本PR的运行时实现中。
