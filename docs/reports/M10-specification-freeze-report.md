# M10 specification freeze report

**Status:** SPECIFICATION FROZEN — REVISION 4; registration and review source in §8.
**Date:** 2026-09-11
**Branch:** `docs/m10-runtime-assurance-spec`
**START_HEAD:** `826d3a7257ad903bc09b0d2d6635a3449576a3ce`
**REVIEWED_HEAD:** `826d3a7257ad903bc09b0d2d6635a3449576a3ce`
**PR_BASE:** `1b44127747a7f7b8bfd9118eb56006d867986b39` (`main`)
**Predecessor milestone:** M9 — Runtime Resilience & Efficiency, specification frozen in `02c1d3f` on branch `docs/m9-runtime-resilience-specs` (published to the remote at revision 3) and merged into this branch

The freeze registration starts at the actual PR head, equal to REVIEWED_HEAD.
Historical revision 4 preparation used
`R4_START_HEAD=9adcddb46f2977ea122966c1167e48fe2592d8be`. Sections 1 and 5 retain
that preparation's file/validation records: their START_HEAD and "this round"
refer to R4_START_HEAD, not the current registration. Historical results are not
reused as current evidence; §8 records the new decision and checks.
M9 declaration-source version is `02c1d3fe9bcd8c95d6bb7cf3959328844598e473`;
other declarations retain their path/clause/source-commit bindings. Source-code
observations below were read at R4_START_HEAD. Future M10 execution evidence must
separately name its actual tested-code commit and effective configuration after
the implementation dependencies are met. START_HEAD identifies this revision's
registration starting point, not a universal source or runtime-verification version.

## 1. Historical files modified while preparing revision 4

| File | Purpose | Revision 4 + / - lines |
| --- | --- | --- |
| `docs/tasks/M10-runtime-assurance-verification.md` | Milestone specification: REQ-M10-1 through REQ-M10-13, boundaries, milestone acceptance, Appendix A, resolved open questions | +88 / -33 |
| `docs/tasks/T-077-guarantee-boundary-ledger.md` | Full task specification for T-077 | +17 / -9 |
| `docs/tasks/T-078-deterministic-failpoints.md` | Full task specification for T-078, with source observations, actual-hit evidence requirements, and scoped marker assertions | +87 / -35 |
| `docs/tasks/T-080-evidence-and-artifact-integrity-audit.md` | Full task specification for T-080 | +70 / -45 |
| `docs/tasks/T-079-run-local-and-project-assurance-reporting.md` | Full task specification for T-079 | +35 / -23 |
| `docs/reports/M10-specification-freeze-report.md` | This report | +145 / -50 |
| `REVIEW-REQUEST.md` | Review instructions, finding dispositions, applied decisions, and remaining gates | +83 / -51 |

This branch additionally carries the M9 specification set (nine files under
`docs/`) via a merge of `docs/m9-runtime-resilience-specs`, so the clauses M10
cites are readable without leaving the pull request.
Those nine files are cumulative PR changes, not files modified in this round.

## 2. Architecture decisions

- **AD-M10-1 — M10 is the complement of M9, not an extension.** M9 governs
  admission and execution-time control. M10 governs ex-post acceptance and
  guarantee verification. No M9 behavior is modified.
- **AD-M10-2 — Verification has four conditions, not one.** Applying
  REQ-M10-2: the source must exist and be the one being verified; evidence must
  actually have been produced; it must match the code version and configuration;
  and its assertions must map to the declaration clause. "A test with this name
  exists" satisfies none of the four by itself.
- **AD-M10-3 — Four ledger states, and `refuted` is preserved.** `verified`,
  `declared`, `refuted`, `not_applicable`. A contradiction may not be relabelled,
  merged, or absorbed into a generic issue bucket.
- **AD-M10-4 — Three verdicts, never one.** Mechanism correctness, claim
  correctness, and closure permission are reported separately. Unexecuted cases,
  missing/wrong actual injection, and incomplete observations fail the mechanism
  and decide neither support nor refutation. A valid counterexample remains
  `violated` / `refuted`. Audit discovery/reporting may complete, but a
  counterexample to required safety (REQ-M10-8 / AC-078-6) fails M10 assurance
  acceptance; a required unverified guarantee cannot pass either. Repairs need
  separate authorization.
- **AD-M10-5 — `undetermined` is decided before execution.** It is assigned from
  reading the contract, never after observing an unexpected result. A
  valid contradiction is always `violated`. An undefined agent-level contract
  does not waive a defined run-safety requirement; skipped or version-mismatched
  evidence never becomes `verified`.
- **AD-M10-6 — `_COMPLETE` is an integrity indicator, not a success indicator.**
  `_finalize_run_directory` runs on both the success path (`runner_multi.py:517`,
  followed by `return 0`) and the failed path (`runner_multi.py:945`, after
  writing partial agent outputs). These are source observations. Marker absence
  at point 4 is required only in an isolated, initially unfinished publication
  interrupted before the marker, with no later completed finalize. Assertions
  concern final files, not temporary files; an old target may survive a fault
  before replacement. Marker presence is neither business success nor a
  substitute for expected-file-set/hash/state checks; marker absence is not
  actual-hit proof. The marker does not automatically detect later file changes
  or deletion (REQ-078-4).
- **AD-M10-7 — Coverage follows the entry point.** A CLI case cannot verify the
  Run API lifecycle contract; `recover_interrupted_runs` is reached from the API
  startup path (`main.py:13`, `main.py:34`, implemented at `runs.py:267`).
- **AD-M10-8 — Citations must be readable from the pull request.** The cited M9
  clauses are present on this branch and published on
  `docs/m9-runtime-resilience-specs`. The original specifications are the
  traceable sources; Appendix A is a reading copy. No repeat publication is
  needed. Readability, M9 implementation completion, M10 freeze, and M10
  implementation permission remain separate; §3 defines the common gate.
- **AD-M10-9 — Excerpt allowance is an allowlist, not an interpretation.** Only
  this repository's own `docs/`, reports, README, and CHANGELOG may be excerpted,
  subject to a length bound and existing sanitization.
- **AD-M10-10 — No recovery, and no multi-process work.** M10 verifies what
  already happens. Resume, compensation, reconciliation, multi-process
  coordination, and process-level crash probing are out of scope; the
  single-process limitation is stated rather than approximated.
  T-080 is limited to contract audit, experiments, ledger, and report. Its
  `models.py`, `store.py`, and `runner_multi.py` objects are read-only; a recorded
  audit decision cannot authorize hash, artifact-format, or persistence changes.
  `tool_call_records` stays outside the current hash projection; equal
  projections are not SHA-256 collisions. Legacy "atomically" is tracked as a
  declaration with a static refutation candidate awaiting valid execution.
  Multi-agent file hashing covers only top-level non-symlink files, excluding
  `_COMPLETE` and `artifact-integrity.json`, with no recursive coverage.

## 3. Task dependencies

| Order | Task | Depends on | Gate evidence required |
| --- | --- | --- | --- |
| 1 | T-077 Guarantee Boundary Ledger and Declaration Registry | Independently approved M10 spec freeze; readable declaration sources; T-070 through T-075 implementation closed | Freeze decision and commit; source path/clause/commit; readable completion report and implementation commit for each dependency below |
| 2 | T-078 Deterministic Failpoint Interface and Interrupt Matrix (Batch 1) | T-077 closed | T-077 completion report path and commit hash |
| 3 | T-080 Evidence and Artifact Integrity Contract Audit | T-078 closed | T-078 completion report path and commit hash |
| 4 | T-079 Run-Local and Project-Level Assurance Reporting | T-078 and T-080 closed | Both completion report paths and commit hashes |
| 5 | Milestone assurance review | T-077, T-078, T-080, T-079 closed | The four completion reports plus the final ledger state |

The required M9 dependencies are identical to REQ-M10-12 and T-077 Status:

| Required implementation | Declaration/dependency basis | Completion evidence at START_HEAD |
| --- | --- | --- |
| T-070 | REQ-M9-4 duplicate ownership; REQ-070-4/-5/-8; predecessor of T-071 | Not satisfied: readable completion report and implementation commit not available |
| T-071 | REQ-M9-4 open circuits; REQ-071-2/-5/-7; predecessor of T-072 | Not satisfied: readable completion report and implementation commit not available |
| T-072 | REQ-M9-4 saturation/no silent discard; REQ-072-3/-4/-6; predecessor of T-073 | Not satisfied: readable completion report and implementation commit not available |
| T-073 | REQ-M9-5 safe observability; REQ-073-5/-7; predecessor of T-074 | Not satisfied: readable completion report and implementation commit not available |
| T-074 | REQ-M9-4 invalid cache entries; REQ-074-3/-5/-7; predecessor of T-075 | Not satisfied: readable completion report and implementation commit not available |
| T-075 | REQ-075-9 failure mapping, directly cited by REQ-M10-1 | Not satisfied: readable completion report and implementation commit not available |

Only their specifications and the M9 specification-freeze report are present;
the required task completion reports and implementation commits are not
available on this PR baseline. No missing report path or SHA is fabricated.
Readability is satisfied; implementation completion remains not satisfied.
Revision 4 specification freeze is registered in §8 using the user-transferred
AI-assisted static re-review; M10 implementation remains blocked by REQ-M10-12.
Unknown or missing dependency evidence must remain explicitly blocked. T-076
Java/Maven is unrelated to this verification scope and is not a gate.

The order remains T-077 → T-078 → T-080 → T-079 → milestone assurance review.
T-080 moved before T-079 in revision 2 and T-081 remains excluded. The current
documentation-only freeze registration may proceed despite the missing future
implementation prerequisites; no T-077 or M9 implementation starts here.

## 4. Unresolved risks

- **R-M10-1 — Required M9 implementation evidence is not satisfied.** The
  sources are readable, but each of T-070 through T-075 still needs a readable
  completion report and implementation commit under §3 / REQ-M10-12. T-077
  also requires independently approved M10 freeze. Neither readable source
  files nor this report meets the implementation gate; T-076 is not required.
  The specification freeze is now registered in §8. This does not implement
  automatic enforcement or authorize an implementation start.
- **R-M10-2 — Baseline observations were read, not executed.** T-078 and T-080
  depend on source-code observations about `_calculate_hash`,
  `_finalize_run_directory`, and `ArtifactStore.write_run`. Both tasks require
  each observation to be confirmed by an executed test or explicitly withdrawn
  (T-078 AC-078-4/-5, T-080 REQ-080-3 / AC-080-3). Legacy success-path file
  count is ten at `artifacts/store.py:43-58`; the case table has seven rows.
  Those counts were checked statically here, not by a new runtime experiment.
- **R-M10-3 — `undetermined` may still dominate.** If existing contracts do not
  define behavior at most Batch 1 interruption points, T-078 will return mostly
  `undetermined`. That is the intended honest outcome, but it may produce a
  milestone that proves little. The milestone assurance review exists to make that
  visible.
- **R-M10-4 — Ledger maintenance burden.** T-077 requires declaration source
  references that resolve mechanically. Renaming a section or moving a report can
  rot a reference into `declared` without any change in real evidence. The ledger
  design must make that failure mode visible rather than silent.
- **R-M10-5 — Batch 1 may mostly restate known limits.** Four interruption points
  may produce four `undetermined` results if the contracts genuinely do not
  define them. Recording those gaps is acceptable audit delivery, not proof of
  required guarantees or permission to mark M10 assurance acceptance passed.
- **R-M10-6 — Interruption points may not be distinguishable in persisted
  artifacts (author finding A3).** Different interruption cases may leave
  similar artifacts, so artifact shape alone must not be used to infer the actual
  injection point; actual test-side hit evidence is required.
  Revision 4 requires test-side actual-hit ID/count/fault/entry evidence,
  generated when the real execution reaches injection, and comparison with the
  preset (REQ-078-12). No hit, wrong point, or wrong count fails the mechanism
  and cannot support or refute the claim. No production manifest/log/business
  field is added. The specification gap is corrected; the mechanism and its
  acceptance tests remain future work, not verified capability.
- **R-M10-7 — This branch now carries two specifications.** Merging the M9 set
  into the M10 branch means this pull request shows the M9 and M10 documents
  together. The M9 documents are frozen and are not open for review here; the
  merge exists solely to make M10's cited clauses readable. A reviewer who treats
  the M9 files as proposed changes would be reviewing the wrong artifact.

## 5. Historical validation evidence for revision 4 preparation

Revision 4 local checks are run in an isolated checkout at START_HEAD plus only
the seven document edits. Python 3.12 and the existing `uv.lock` are used with
`UV_FROZEN=true`; no dependency update or live-provider run is requested.

| Command / scope | Actual result | Exit code |
| --- | --- | --- |
| Baseline `uv run pytest -v` at START_HEAD before edits | 771 passed, 3 skipped, 3 warnings in 27.57s | 0 |
| Revision 4 `uv run pytest -v` | 771 passed, 3 skipped, 3 warnings in 10.86s | 0 |
| Revision 4 `uv run ruff check .` | All checks passed; existing invalid `# noqa` warning at `tests/test_coordinator.py:113` | 0 |
| Revision 4 `uv run ruff format --check .` | 208 files already formatted | 0 |
| Revision 4 `git diff --check` | No whitespace errors; repeated after this report's final edit | 0 |
| Revision 4 scope/reference static check | Exactly seven existing allowlisted files; no additions/deletions/renames or untracked files; REQ/AC IDs resolve; seven case rows and ten legacy writes | 0 |

The three pytest skips concern Windows symlink privileges
(`test_repository_tools.py:238`, `test_runs.py:204`, `test_scanner.py:148`). The
three warnings are collection warnings for `TestStrategyAgent` and
`TestStrategyOutput`, plus the Starlette/httpx deprecation warning. Baseline and
revision 4 runs report the same skip/warning categories. None was hidden or
changed to obtain a passing gate.

Final diff: START_HEAD to revision 4 is **7 files, 525 insertions,
246 deletions**; PR_BASE to revision 4 is **16 files, 2505 insertions,
0 deletions**. File-level changes are listed in §1. The deleted lines are scoped
text replacements; no file is deleted. All seven changed paths are allowlisted;
the nine M9 files and all runtime, test, dependency, CI, benchmark, script,
prompt, and evaluation paths are unchanged in this round. No pre-existing user
work was included. The isolated original repository's untracked report remains
outside this checkout and commit.

Raw local command logs (`baseline-pytest.log`, `pytest.log`, `ruff-check.log`,
`ruff-format.log`, `diff-check.log`, and `scope-check.log`) and command exit codes
are retained outside the checkout in `C:/Users/50469/temp/specflow-pr6-m10-20260911`.

The cumulative baseline PR contains 16 files / 2226 insertions / 0 deletions:
seven M10/review documents plus nine previously merged M9 documents. The nine
M9 files are not modified in this round. Earlier revision results are historical
provenance only and are not reused as revision 4 execution evidence.

These existing quality checks do not verify the future M10 failpoints, audits,
or assurance reporting. Remote CI for the resulting commit is checked after
push and reported in the PR; no pre-commit remote result is asserted here.

## 6. No-runtime-implementation confirmation

This branch contains documentation only. No file under `src/`, `tests/`,
`benchmarks/`, `scripts/`, `prompts/`, or `evaluation/` is added or modified, and
no dependency manifest is changed. The M9 merge commit `5df7462` adds nine
documents under `docs/` and nothing else.

## 7. Revision history

| Revision | Commit | Change |
| --- | --- | --- |
| 1 | `0ee6046` | Initial draft: milestone plus T-077 and T-078 full specs, boundary-only T-079 through T-081 |
| 2 | `010b024` | Addresses the PR #6 review: four-condition verification semantics, four ledger states with `refuted` preserved, three separate verdicts, pre-execution `undetermined`, evidence-backed dependency gates, Appendix A citation reproduction, excerpt allowlist, boundary-separated read-only rule, normalized determinism, corrected `_COMPLETE` semantics, entry-point coverage table, closed fault set, failpoint registration isolation, T-079 dimension separation, T-080 narrowing and reordering, T-081 removal |
| 3 | `5df7462`, `ab14b9a`, `9adcddb` | Made M9 sources readable: the branch was published, the M9 specifications merged, and REQ-M10-6 / row-1 citation evidence revised. The separate implementation gate still required the revision 4 correction |
| 4 | `826d3a7257ad903bc09b0d2d6635a3449576a3ce` | Align implementation gates and source/code/revision bindings; distinguish audit delivery from assurance acceptance; require actual test-side hits; scope marker assertions; separate reporting dimensions; close audit runtime-change permissions; apply resolved decisions and factual corrections |
| 4 freeze registration (2026-09-11) | One focused registration commit after REVIEWED_HEAD; its SHA is recorded in the PR body and registration comment | Register the user-transferred ChatGPT AI-assisted static re-review and user's freeze decision; synchronize status while preserving implementation gates; narrow R-M10-6's artifact-shape observation |

Revision 3 comprised merge `5df7462`, text revision `ab14b9a`, and provenance
update `9adcddb` (R4_START_HEAD). Revision 4 makes Appendix A a reading
copy and separately requires implementation completion; it does not rewrite a
historical review verdict. The new revision commit's own SHA is
recorded after commit in the PR, without an extra provenance-only commit.

## 8. Revision 4 freeze registration

### 评审依据与登记决定（2026-09-11）

- 被审规范提交（REVIEWED_HEAD）：`826d3a7257ad903bc09b0d2d6635a3449576a3ce`。
- 本次登记起点（START_HEAD）：`826d3a7257ad903bc09b0d2d6635a3449576a3ce`；开始时 PR #6 为 OPEN，远端 head 未超出被审提交。
- PR_BASE：`1b44127747a7f7b8bfd9118eb56006d867986b39`（`main`）。
- 评审来源与性质：用户转交的 ChatGPT AI 辅助静态复审意见，针对上述固定提交；本执行者负责登记，不声称又完成了一次独立评审，也不冒充人类评审人。

用户转交的结论原文：

> 针对固定提交 826d3a7257ad903bc09b0d2d6635a3449576a3ce，revision 4 通过 AI 辅助静态复审，建议批准 M10 规范冻结。R1/R2/R3、C1、S1/S2/S3 的规范问题可以关闭。该结论不代表 M9/M10 实现已完成，不代表 M10 保障验收通过，也不代表 GitHub 正式 APPROVE 或 PR 已合并。

依据该复审意见及用户本次明确授权，登记 revision 4 规范冻结。仓库规则与
REQ-M10-12 的实现门槛保持不变；所读取规则未规定额外的指定评审身份或 GitHub 正式
APPROVE 才能登记规范冻结。本次不执行 GitHub APPROVE、合并或自动合并，
不将此次评审扩展为对 PR 内 M9 原有文档的重新批准。此前的待审状态、执行者
自检及质量检查保留为历史记录，不改写为此前已经通过。

### 规范问题结算与冻结范围

| 规范问题 | 本次登记状态 | 仍需满足的后续条件 |
| --- | --- | --- |
| R1 | 依据引用的静态复审关闭 | T-070～T-075 各自的实现完成证据仍未满足 |
| R2 | 依据引用的静态复审关闭 | 机制、声明和保障验收仍须后续有效实验分别判断 |
| R3 | 依据引用的静态复审关闭 | 实际命中证据机制及验收测试尚未实现或验证 |
| C1 | 依据引用的静态复审关闭 | 带前置条件的标记、文件集合、哈希和运行状态断言仍待实验 |
| S1 | 依据引用的静态复审关闭 | 两个报告维度的行为仍待实现和测试 |
| S2 | 依据引用的静态复审关闭 | 后续 T-080 审计仍须遵守运行时只读边界 |
| S3 | 依据引用的静态复审关闭 | 静态反驳候选及其他未来实验要求未变成已验证能力 |

冻结的是规范，具体细化程度遵循 AC-M10-1：T-077/T-078 规范冻结；T-079/T-080
冻结范围、入口与判据，字段级细化仍须在前置任务关闭后完成并通过各自冻结门。
不宣布所有细节已经完成，也不宣布 M9 或 M10 里程碑实施完成、M10 保障验收通过。

### 当前实现门与本次修改范围

REQ-M10-12 继续约束全部 M10 实现。声明源可读，但 §3 列出的 T-070、T-071、
T-072、T-073、T-074、T-075 均未提供所需的可读完成报告和实现提交，仍为
**Not satisfied**；T-076 不属于该门。T-077 因此保持阻塞，T-078 仍须 T-077
关闭，T-080 仍须 T-078 关闭，T-079 仍须 T-078 与 T-080 关闭，并分别满足规范
冻结、质量门和新会话条件。本次不启动 T-070、T-077 或其他实现。

本次只修改现有七份 M10/review 文档的状态、评审结算、冻结登记与许可说明：

- `REVIEW-REQUEST.md`
- `docs/tasks/M10-runtime-assurance-verification.md`
- `docs/tasks/T-077-guarantee-boundary-ledger.md`
- `docs/tasks/T-078-deterministic-failpoints.md`
- `docs/tasks/T-079-run-local-and-project-assurance-reporting.md`
- `docs/tasks/T-080-evidence-and-artifact-integrity-audit.md`
- `docs/reports/M10-specification-freeze-report.md`

唯一非状态修正位于 R-M10-6：不同中断案例可能留下相似产物，因此不得仅凭
产物形态推断实际注入位置；必须使用测试端实际命中证据。该文字遵循
REQ-078-12，不改变 failpoint 范围、异常处理或验收要求。

### 本次实际质量检查

以下检查在干净的现有 M10 worktree 上，以 START_HEAD 加本次文档修改运行，
使用 Python 3.12.10、现有 `uv.lock` 和 `UV_FROZEN=true`。未更新依赖，
未运行 live provider；§5 历史结果不作为本次证据。

| 命令／检查 | 本次实际结果 | 退出码 |
| --- | --- | --- |
| `uv run pytest -v` | 771 passed, 3 skipped, 3 warnings in 11.54s | 0 |
| `uv run ruff check .` | All checks passed! | 0 |
| `uv run ruff format --check .` | 208 files already formatted | 0 |
| `git diff --check` | 通过，无空白错误 | 0 |
| `git diff --cached --check` | 提交前检查通过，无空白错误 | 0 |
| 本轮范围与状态核对 | 仅七份现有许可文档；无新增、删除、重命名或未跟踪文件；任务正文、AC-M10-1/验收条款及依赖门保持不变；新增内容未发现机器绝对路径或凭据模式 | 0 |

三项跳过分别位于 `tests/test_repository_tools.py:238`、`tests/test_runs.py:204`、
`tests/test_scanner.py:148`，原因是 Windows 符号链接权限。三项警告为
`TestStrategyAgent`、`TestStrategyOutput` 的 pytest 收集警告，以及 Starlette/httpx
弃用警告。本轮 Ruff 输出没有警告；未复制上一轮的警告或耗时作为本次结果。
完整命令日志保留在仓库之外，原始输出未进入提交。

本轮 diff 无 M9 规范、运行时代码、测试、依赖、锁文件、CI、基准或其他范围外
改动。质量检查是现有回归与静态检查，不是尚未实施的 M10 保障验收证据。
冻结登记提交自身的 SHA 在提交后写入 PR 正文、登记评论和交付记录，不追加
循环 provenance 提交。完成登记与发布后停止。
