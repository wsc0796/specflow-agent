# T-077 — Guarantee Boundary Ledger and Declaration Registry

> **修订说明（2026-09-13）：AMENDMENT PROPOSED / 待重审。** 来源为
> PR #12 固定提交 `558004b2bfc46ddcf76317ba30123a12f486445f` 的外部规范重审
> S12-04 / P2。本次补齐 determinism 的 evidence-input-set 边界，不代表实现
> 完成或 dependency gate 已满足。下方 REVISION 4 为既有冻结记录；本修订尚待
> 重审，不改变 REQ-M10-12 或放行 T-077。

> **后续修订（2026-09-13）：AMENDMENT PROPOSED / 待重审。** 固定提交
> `a178735b335628d650e9755c91545c94af926c9b` 的复审发现 R12-02 / P2 接续
> S12-04：保留完整输入确定性，将反证保留限定在显式 evidence snapshot 及其
> 判断谱系内，不引入跨运行历史存储。本次不代表实现完成或实施门已满足。

**Status:** SPECIFICATION FROZEN — REVISION 4. Implementation is blocked until the
full REQ-M10-12 gate is satisfied: independently approved M10 specification
freeze (decision and commit), readable declaration sources at their named source
commits, and a readable completion report plus implementation commit for **each
of T-070 through T-075**. At the freeze-registration START_HEAD the sources are
readable, but those six implementation dependencies remain not satisfied.
Revision 4's specification freeze is registered using the user-transferred
ChatGPT AI-assisted static re-review in the
[freeze report §8](../reports/M10-specification-freeze-report.md#8-revision-4-freeze-registration).
T-076 is not required by this scope. If a source or dependency cannot
be established, record the specific gap and keep the entry blocked; do not guess.
Source readability and document freeze do not substitute for implementation
completion or authorize an implementation start. This gate does not block the
current documentation-only freeze registration. Execution requires a new focused
session after the full gate is satisfied.

## Goal

Extract the runtime guarantee declarations currently scattered across
specifications, reports, and the README into one versioned, mechanically
checkable declaration registry, and bind each declaration to its evidence source
and current judgement state, so that "claimed to hold", "demonstrated to hold",
and "contradicted" become distinguishable by machine.

## Requirements

### Declarations and sources

- **REQ-077-1 — Extract, do not invent.** Every ledger entry carries a
  declaration source reference (file path plus section or identifier) and the
  declaration's own bounded identifier and declaration-source commit, separate
  from the tested-code commit/configuration and revision START_HEAD. A
  declaration with no reproducible source must not be added.

- **REQ-077-2 — Stable declaration identity.** Each declaration has a stable ID,
  a bounded category (security, boundary, failure semantics, integrity,
  single-process limit), and a short bounded description. These fields are
  subject to REQ-M9-5.

- **REQ-077-3 — Excerpt allowance is explicit, not interpretive.** The ledger may
  store a bounded excerpt only from **SpecFlow's own curated declaration
  sources**: files this repository maintains — specifications under `docs/`,
  completion reports under `docs/reports/`, the README, and the CHANGELOG.
  Excerpts must never be taken from an analyzed target repository, from
  `EvidenceBundle` content, from tool output, from prompt text, or from provider
  responses. The excerpt field is bounded by a configured maximum length and
  passes the existing sanitization and DLP rules. Where an excerpt is not stored,
  the entry carries the source reference, declaration ID, and a bounded
  human-written description instead. This requirement explicitly resolves the
  apparent conflict between storing excerpts and the REQ-M9-5 content
  prohibition by defining what an excerpt is allowed to be.

- **REQ-077-4 — Evidence references must resolve to produced evidence.** An
  evidence reference points at a concrete test node, report path, or command
  **together with a recorded execution outcome and the commit or version it was
  produced against, including its effective configuration**. The execution
  binding is separate from the declaration-source version. Applying REQ-M10-2:

  | Situation | Required state |
  | --- | --- |
  | Declaration exists; no evidence targets it | `declared` |
  | Evidence exists and was produced; version binding matches; assertions map to the declaration clause | eligible for `verified` |
  | Test node or command name exists but no recorded execution outcome | `declared` — never `verified` |
  | Evidence was produced against a different commit or configuration | `declared` — never `verified` |
  | Evidence is a skipped or conditionally disabled test | `declared` — never `verified` |
  | Valid recorded evidence contradicts the declaration (fault cases satisfy REQ-M10-4; static audit candidates follow REQ-080-4) | `refuted` |
  | Declaration does not apply to the verified configuration | `not_applicable` |

  参与判断的证据来自 REQ-077-8 的显式 evidence-input-set snapshot，不得隐式
  扫描新生成的 ledger 来替代实际 execution evidence。同一 checkout 后续显式
  提供有效证据，可以使 `declared` 依法变为 `verified`，但仍须逐项满足
  REQ-M10-2 的四条件；skipped、version-mismatched 或 unexecuted evidence
  均不能产生 `verified`。在同一个 explicit evidence-input-set snapshot 中，
  有效反证必须产生 `refuted`；该 snapshot 产生的 normalized ledger、rollup 和
  summary 均须保留它，不能因同集合中也有支持证据而降级或隐藏。
  另一份 evidence snapshot 是新的判断输入，必须按 REQ-077-8 显示不同的
  `evidence_set_id`。本任务不维护独立历史真相源，因此不承诺仅凭当前集合自动
  检测或报告“过去的反证已被删除”，也不能据此声称跨运行 anti-removal。

- **REQ-077-5 — Judgement and justification are separate fields.** The ledger
  records the state (`verified`, `declared`, `refuted`, `not_applicable`) and its
  basis separately. `verified` is not permitted while any of the four
  REQ-M10-2 conditions is unmet.

- **REQ-077-6 — `refuted` is preserved through every rollup.** A contradiction
  must survive aggregation. No summary, count, percentage, or score may fold
  `refuted` into `declared`, `unverified`, `not_applicable`, or any "known
  issues" bucket that is not separately reported. Downgrading a judgement so a
  summary reads better violates REQ-M10-5.
  此保证覆盖同一显式 evidence snapshot 及其产生的全部 assurance evidence
  lineage：重复生成、汇总或展示均不能隐去该集合的 `refuted`。若并列展示不同
  evidence set，须按 `evidence_set_id` 区分判断及其来源，不能用新集合的结论
  覆盖、冒充旧集合的连续判断。该规则不隐含自动检索历史集合或累积存储能力。

### Validation mechanics

- **REQ-077-7 — Validation is offline and read-only with respect to everything
  except its declared output directory.** The validation command calls no LLM,
  performs no network access, and scans no unauthorized path. It does not modify
  the target repository, does not modify SpecFlow's tracked sources, and does not
  modify any existing run artifact. It writes only inside an explicitly provided
  output directory, through the existing safe-artifact boundary. This
  requirement distinguishes three separate things that revision 1 conflated:

  | Boundary | Rule |
  | --- | --- |
  | Target repository under analysis | Read-only, always |
  | Validation computation itself | No writes outside the declared output directory |
  | Ledger output | Writable, but only inside the explicitly provided output directory |

- **REQ-077-8 — Determinism is defined over normalized content, not the whole
  package.** 确定性以完整输入为条件：

  ```text
  Normalized Ledger = f(
    declaration registry/source snapshot,
    tested-code commit + effective configuration,
    explicit evidence-input-set snapshot + evidence_set_id,
    judgement-rule/schema version
  )
  ```

  相同完整输入必须产生相同 normalized ledger content，包括 declarations、
  states、evidence references 和 ordering，仅排除 volatile fields。仅有相同
  checkout 不足以要求相同判断；evidence input set 改变时，judgement 可以按照
  REQ-077-4/-5/-6 和 REQ-M10-2 改变。
  evidence set 必须显式、有界、可版本绑定、可重现：记录规范排序的成员清单、
  可解析的证据引用及内容/版本身份、实际执行结果与 tested-code/config 绑定；
  空集合也须明确表示。每个集合使用稳定、有界的 `evidence_set_id`，由规范化的
  evidence manifest 内容计算抗碰撞摘要（例如 SHA-256），并核验 ID 与实际 manifest
  一致。成员清单、证据内容/版本或执行绑定变化必须改变 ID；不得对不同集合复用
  人工标签来伪装同一身份。manifest 是当前显式输入的描述，不是新增的累积历史库。
  该 ID 进入 normalized ledger 输入身份，并在 ledger 及其 rollup/summary 中
  可见；不同集合即使得到相同 judgement，也必须显示不同 ID。
  不同 evidence set 的后续执行可以依法产生不同 judgement，但不得宣称与旧集合
  属于同一连续 evidence lineage。相同完整输入（包括相同 ID）仍须得到相同
  normalized ledger。重现须使用同一固定集合，不能把“目录当前有哪些文件”
  当作未记录的隐式输入。当前输出 ledger 及其完成标记不自动成为下一次运行的
  输入，避免 self-referential result drift；ledger 状态本身不替代底层有效证据。
  已有完成标记的 `completed_at` 来自 wall clock，仍不要求整个包字节相同；
  比较对象为 normalized ledger body，不包括外围易变 package metadata。

- **REQ-077-9 — Conform to the existing artifact boundary.** The ledger artifact
  is written through the existing safe-artifact boundary (atomic write,
  integrity hash, completion marker) and obeys the existing DLP rules and size
  limits.

### Surface and scope

- **REQ-077-10 — Expected implementation surface.** Expected production files are
  a focused `src/specflow/assurance/ledger.py`, `src/specflow/assurance/models.py`,
  and the minimum CLI wiring in `src/specflow/cli.py`. Expected tests are
  `tests/test_assurance_ledger.py` and `tests/test_cli.py`. If validation would
  require an LLM, network access, a new dependency, or write access outside the
  declared output directory, stop and amend the specification with evidence
  before editing.

- **REQ-077-11 — The first declaration set must cover the named boundary
  clauses.** Batch 1 must include: fail-closed required-agent behavior; no silent
  discard (M9 REQ-M9-4); the observability content boundary (M9 REQ-M9-5); the
  single-process guarantee (M9 REQ-M9-6); artifact integrity **as actually
  implemented in each pipeline**; mock-mode determinism; and repository
  read-only behavior.

  Artifact integrity must be listed as **two separate declarations**, because the
  two pipelines do not provide the same guarantee:

  | Declaration | Source of truth |
  | --- | --- |
  | Multi-agent run directory integrity | `runner_multi.py` `_finalize_run_directory`: per-file SHA-256 in `artifact-integrity.json`, completion marker written last, per-file atomic replace |
  | Legacy linear run directory integrity | `artifacts/store.py` `ArtifactStore.write_run` |

  Several entries are expected to be `declared` rather than `verified`. Recording
  that honestly is the deliverable, not a shortfall.

## Boundaries

The following are explicit non-goals for T-077:

- Do not implement fault injection (that is T-078). The ledger may reference
  evidence that does not yet exist, but must mark it `declared`.
- Do not parse natural language to "understand" declarations. Use bounded
  deterministic matching plus an explicit maintainable list.
- Do not change any product runtime behavior, topology, schema, DLP rule,
  policy, or artifact contract.
- Do not add a dependency, call an LLM, or access the network.
- Do not retroactively edit existing reports or specifications to make a
  reference resolve.
- Do not attach an improvement roadmap or remediation promise to a `declared` or
  `refuted` entry.
- Do not decide that a declaration holds because a similarly named test exists.
  REQ-077-4 governs.
- 不新增 cumulative evidence history、跨运行 anti-removal 或历史删除/回滚检测。
  如需此类保证，必须另行明确权威 manifest 的创建者、更新者、存放位置、版本化、
  输入绑定、离线只读边界及删除/回滚验收，并取得范围批准；输出 ledger 不充当
  隐式历史真相源。

## Acceptance

- **AC-077-1:** The ledger contains every declaration listed in REQ-077-11, each
  with a reproducible source reference, stable ID, bounded category, and state.
- **AC-077-2:** Tests prove each REQ-077-4 row is enforced: a resolvable-but-
  unexecuted reference, a version-mismatched reference, and a skipped test each
  yield `declared`, not `verified`.
- **AC-077-3:** A test proves a `refuted` entry survives aggregation and is not
  merged into `declared`, `not_applicable`, or a generic issues bucket.
- **AC-077-4:** A test proves an excerpt taken from an analyzed target
  repository, from `EvidenceBundle` content, or from prompt text cannot enter the
  ledger, while an excerpt from a curated `docs/` source can, subject to the
  configured length bound.
- **AC-077-5:** 测试按 REQ-077-8 的完整输入验证以下情形；比较 normalized body，
  package completion marker 可以不同：
  - same declaration/source + same tested-code/config + same evidence set 及
    evidence_set_id + same judgement rules/schema → normalized result identical；
  - new evidence set 的 membership、证据内容/版本或执行绑定变化 → evidence_set_id
    visibly changes；不匹配的 manifest/ID 不能被接受为同一输入身份；
  - same checkout，显式提供另一集合且其有效证据满足 REQ-M10-2 四条件 →
    judgement 可以依法不同，例如 `declared` 变为 `verified`；必须展示新 ID，
    不得冒充旧集合的同一连续判断，或据此重标记旧集合中的 `refuted`；
  - 仅提供 skipped、version-mismatched 或 unexecuted evidence → 仍为 `declared`，
    不得 `verified`（同一集合内有有效反证时仍按下一项保留 `refuted`）；
  - same evidence set contains valid refutation → 每次 normalized ledger 生成及
    每个 rollup/summary 均保留 `refuted`，不合并或隐藏；
  - evidence set 的成员/内容/版本绑定可重现且有界；输出 ledger 的出现或
    completion marker 的时间变化不自动改变下一次输入或 normalized result。
- **AC-077-6:** Tests prove the command writes only inside the declared output
  directory and modifies no target repository file, no tracked source, and no
  existing run artifact.
- **AC-077-7:** The ledger artifact obeys the existing atomic-write, integrity
  hash, and completion-marker contract.
- **AC-077-8:** Existing CLI/mock, artifact, DLP, policy, and benchmark tests
  remain green.
- **AC-077-9:** Targeted tests pass, followed by `uv run pytest -v`,
  `uv run ruff check .`, `uv run ruff format --check .`, and
  `git diff --check`.
- **AC-077-10:** `docs/reports/T-077-completion-report.md` records the
  declaration list, source mapping, state distribution including every `refuted`
  entry, the excerpt allowance as implemented, validation semantics, and known
  limits. One focused commit is created, then work stops before T-078.
