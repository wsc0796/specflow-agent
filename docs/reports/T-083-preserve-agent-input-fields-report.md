# T-083 完成报告 — 实际上游输入交付（F1）

- 日期：2026-09-26；规格：[T-083](../tasks/T-083-preserve-agent-input-fields.md)。
- 状态：本项实现与相关验证完成；五项最终全量记录于本轮统一验证报告。

删除完整JSON截前500字符的路径，序列化已有 validated_input 中接收者声明的完整上游payload。
通过既有 TokenEstimator 估算 system+user 全部文本；超出当前 policy.max_agent_input_tokens 时
在 LLM 调用前明确抛出 TOKEN_BUDGET_EXCEEDED。没有增大 Context 全局预算或修改 payload Schema。

| AC | 状态 | 实际证据 |
| --- | --- | --- |
| AC-001 | PASS | 700字符summary之后 key_files 到达全部Specialists，implementation_steps/test_scenarios/risks到达Synthesis，实际JSON可解析且summary完整 |
| AC-002 | PASS | 5000字符合法summary＋1024输入估算额度：exit3、只发6 briefs+1 Analyst共7次，保留Stage0；raw Evidence不流入Specialists/Synthesis |

证据根沿用本批 `specflow-repair-backups/2026-09-26-integration-audit-T082-T086`。
`validate.py t083-red -v tests/test_agent_input_delivery.py`：6 failed，证明字段丢失、输入超限未拒绝及
预算参数未支持。`t083-green` 包含新测试、test_agent_adapter、test_cli_multi_agent、T-078失败审计、
T-079请求预算及T-082 CLI，共91 passed；真实 HTTP=0。Ruff/format/diff 与规格追溯通过。

4字符/token 是项目已有确定性估算，不能当作实际Provider计量保证；T-079响应usage检查仍有效。
过大必要输入选择明确失败，没有静默字段级裁剪。只提交adapter、runner接线、新测试、规格/报告。
回退 `git revert <引入本报告的提交>`；不推送，不回写旧评分或正式数据。
