# 契约审查公开回归材料

这是 PLAN-CR-V02-PUBLIC-01 的已知公开样例，不是独立留出。
`cases.json` 仅列六个早期输入；`materials/` 保存实际业务正文。
将每个 sources[].fixture 的字节复制到 sources[].path 后，在隔离临时仓库
形成固定 commit，再把该 SHA 和临时 project_id 填入创建请求。被查应用只读不执行。

`oracles.json` 单独保存预先写出的判据；`human-scripts.json` 保存 H01/H02
在正式归属问题出现后的人工答案。两者均不得加入 source groups 或初始模型请求。
Oracle 由 Codex 根据已批准规格整理，尚未由用户独立复核，不能声称专家一致性。

`manifest.json` 保留全部 24 个原 case/trial/sample 身份及本次选择。
六例 READY 仅表示材料准备好；所有语义结果仍 NOT_RUN。未准备的 COMMON
案例继续保留，R03/R05 因未选项目记忆排除。真实模型/profile/预算均未获准，保持 null。

旧资产迁移沿用外部交接 `V0_2_TEST_ASSET_MAPPING_2026-10-30.md` 的 M01—M24。
本轮六例主要承接 M19 的新业务材料与 M05 的答案实际送达检查；没有读取、复制
或运行旧 H04/六轨回答。旧 PASS 不继承。具体来源索引见本轮完成报告。
