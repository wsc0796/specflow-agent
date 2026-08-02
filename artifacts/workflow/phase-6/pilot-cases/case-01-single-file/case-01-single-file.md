# Pilot Case 01 — 单文件

- 聚焦:app/orders.py(订单取消)。
- 期望证据:对 orders.py 内函数/状态字段的精确引用;状态机表;校验规则;错误契约。
- 盲评关注:范围克制(不扩散到 auth/catalog)、状态机完备性、测试计划可执行性。
- 自动化判定:expected_file_patterns 命中 app/orders.py;expected_risks 覆盖率;schema_valid。
