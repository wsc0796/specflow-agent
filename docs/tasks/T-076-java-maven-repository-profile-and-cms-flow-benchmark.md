# T-076 — Java/Maven Repository Profile and `cms-flow` Benchmark

**Status:** FROZEN. Implementation requires closed T-070 through T-075, an
approved M9 runtime review, and a new focused session.

## Goal

Explicitly authorize and implement a bounded Java/Maven repository-understanding
profile, then validate it against a small sanitized `cms-flow`-derived fixture
and five deterministic evidence cases without turning SpecFlow into a general
compiler, Maven runner, or polyglot parser platform.

## Requirements

- **REQ-076-1 — Treat this spec as the authorization boundary.** This frozen
  task is the explicit authorization for the listed Java/Maven scope expansion
  after the T-070–T-075 runtime review. Implementation must update
  `docs/00-SPEC-BASELINE.md`, `AGENTS.md`, README/current claims, and the
  completion report to describe the limited profile. It must not infer broader
  polyglot support.
- **REQ-076-2 — Keep language detectors modular.** Preserve the existing Python
  behavior behind a focused Python detector, add a separate Java/Maven detector,
  and keep `TechnologyStackDetector` as a small façade/coordinator. Do not grow
  one giant detector with interleaved Python and Java branches. Mixed-language
  repositories are not required; if both supported profiles are present, return
  an explicit deterministic ambiguity/unsupported warning rather than guessing
  or merging contracts.
- **REQ-076-3 — Recognize only evidence-backed Java/Maven facts.** From safe,
  bounded repository files recognize:
  - root and declared-module `pom.xml` files and Maven multi-module structure;
  - Java source presence from `*.java`;
  - Java version from supported `<java.version>`,
    `maven.compiler.source`, `maven.compiler.target`, or
    `maven.compiler.release` properties;
  - Spring Boot parent/dependencies/plugin where explicit;
  - JUnit/Jupiter or `spring-boot-starter-test` test support;
  - selected exact dependencies for Redis, Caffeine, and Resilience4j; and
  - the presence of bounded `application.yml`, `application.yaml`, or
    `application.properties` configuration files.
  Every detected fact must carry a real relative file locator and bounded
  matched evidence. Missing or unresolved data remains unknown.
- **REQ-076-4 — Parse Maven safely and incompletely on purpose.** Use Python
  standard-library/local parsing over files already admitted by the safe scan.
  Reject or ignore DOCTYPE/external entities, never resolve network resources,
  and bound file count/size/module depth. Support only direct root/module
  relationships and named properties/dependencies above; do not emulate Maven
  inheritance, profiles, plugins, repositories, transitive resolution, or full
  property interpolation.
- **REQ-076-5 — Align repository safety layers.** Update both metadata scanner
  and read-only repository-tool policy to exclude generated/IDE content
  consistently, including case variants of `target/`, `.idea/`, and `*.iml`.
  Extend evidence file patterns narrowly for `pom.xml`, `*.java`, and supported
  Spring configuration files while preserving sensitive-file, symlink/reparse,
  size, count, path, and DLP boundaries.
- **REQ-076-6 — Preserve Python and existing benchmark contracts.** All existing
  Python detector/scanner/tool/evidence tests and the committed 12-case mock
  portfolio baseline remain unchanged in meaning. Additive Java fields use safe
  defaults so Python serialization remains compatible. Do not rewrite the
  historical portfolio baseline as Java evidence.
- **REQ-076-7 — Build a sanitized fixture, not a repository dump.** Create
  `benchmarks/fixtures/cms-flow-java/` from the authorized reference using only
  the minimal POMs, Java exemplars, and sanitized application configuration
  necessary to prove the supported facts. Exclude `target/`, `.idea/`, `.mvn/`,
  `.feisuan/` and all project/AI instruction files, compiled classes, generated
  sources, credentials, local workspace files, logs, unnecessary stubs, and
  unrelated business assets. The fixture must pass the tracked-file credential
  scan and must not contain answer-leaking instructions.
- **REQ-076-8 — Add five deterministic Java/Maven cases.** Add a dedicated suite
  separate from the existing exactly-12-case portfolio suite, with expected
  evidence for:
  1. root Maven aggregator and declared modules;
  2. Java 21 and Spring Boot recognition;
  3. Redis, Caffeine, and Resilience4j dependency evidence;
  4. Java source/test-support and application-config evidence; and
  5. generated/IDE exclusion plus end-to-end mock evidence grounding.
  Cases must assert structure, relative evidence locators, safe exclusions, and
  stable hashes. They must not use an LLM judge or require a live provider.
- **REQ-076-9 — Keep benchmark execution deterministic.** A dedicated loader or
  explicit suite manifest may support the five-case profile suite without
  weakening the existing 12-case cardinality/category gate. The benchmark may
  exercise the existing mock multi-agent pipeline after Java evidence support is
  added, but it must not compile Java, invoke Maven, download dependencies, start
  Spring, call network services, or modify the fixture.
- **REQ-076-10 — Define failure semantics.** Unsafe or unsupported XML,
  malformed/oversized metadata, missing modules, ambiguous mixed-language
  input, and fixture-contract violations must produce stable warnings or safe
  classified failures without partial evidence being presented as confirmed.
  One failed benchmark case remains a failed deterministic case with bounded
  error codes; it must not fall back to guessed technology or an LLM judgment.
- **REQ-076-11 — Expected implementation surface.** Expected production files
  include `src/specflow/scanner.py`,
  `src/specflow/tools/repository_policy.py`,
  `src/specflow/evidence/collector.py`, `src/specflow/technology.py`, one focused
  Java/Maven detector/profile module, `src/specflow/evaluation/benchmark.py`,
  and minimal CLI/profile serialization integration. Expected tests include
  `tests/test_java_maven_profile.py`, `tests/test_technology.py`,
  `tests/test_scanner.py`, `tests/test_repository_tools.py`,
  `tests/test_evidence_collector.py`, and `tests/test_benchmark.py`, plus the
  sanitized fixture, five case files, and a normalized deterministic baseline if
  the benchmark contract requires one. Files outside this surface require a
  spec amendment before editing.

## Boundaries

The following are explicit non-goals for T-076:

- Depends on an approved milestone review after T-070 through T-075. This task
  must not start in the same implementation session as T-075.
- No Gradle, Kotlin, Android, Scala, Groovy, Ant, arbitrary XML/YAML semantics,
  general polyglot support, compiler frontend, AST platform, Maven invocation,
  build/test execution, dependency download, or transitive resolution.
- No Java code generation or modification, no target-repository write, and no
  running fixture application or network service.
- No copying `cms-flow` production code into SpecFlow runtime. The fixture is a
  minimal sanitized evidence corpus only.
- No `target/`, `.idea/`, `.mvn/`, `.feisuan/`, `*.iml`, `.class`, generated
  source, credential, local config, instruction/rule, or unnecessary business
  asset in the committed fixture.
- No live-provider benchmark, model-quality claim, production-readiness claim,
  or claim that the profile understands all Maven/Spring projects.

## Acceptance

- **AC-076-1:** Python detector output and all existing Python/scanner/tool/
  evidence tests remain compatible; Java logic is isolated behind a focused
  detector/profile seam.
- **AC-076-2:** Unit tests detect the exact supported Maven modules, Java version,
  Spring Boot, JUnit/test support, Redis, Caffeine, Resilience4j, Java sources,
  and application config with real relative evidence.
- **AC-076-3:** Missing POM fields, malformed/oversized POM, unsupported
  interpolation/profile, DOCTYPE/external entity, undeclared module, mixed
  Python/Java, and unknown dependency cases fail safely or return explicit
  warnings without guessing.
- **AC-076-4:** Scanner and repository-tool tests prove case-insensitive
  `target/`/`.idea/` exclusion, `*.iml` exclusion, no symlink/reparse escape,
  and bounded Java/POM/config reads.
- **AC-076-5:** The committed fixture contains only the approved minimal source
  set. Automated assertions and diff review prove forbidden generated, IDE,
  instruction, credential, compiled, and unnecessary files are absent.
- **AC-076-6:** Exactly five dedicated Java/Maven cases pass with stable expected
  evidence and hashes; the existing 12-case normalized portfolio benchmark also
  passes unchanged in meaning.
- **AC-076-7:** Tests prove no subprocess/Maven/compiler/network call and no
  fixture modification during detection or benchmark execution.
- **AC-076-8:** Targeted tests pass, followed by `uv run pytest -v`,
  `uv run ruff check .`, `uv run ruff format --check .`,
  `python scripts/check_secrets.py`, and `git diff --check`.
- **AC-076-9:** Baseline, AGENTS, README/current claims, task report, and
  benchmark documentation describe only the bounded Java/Maven profile and
  distinguish mock contract evidence from live-provider validation.
- **AC-076-10:** `docs/reports/T-076-completion-report.md` records the exact
  supported evidence, fixture provenance/sanitization, five cases, regression
  evidence, and known limits. One focused implementation commit is created,
  then work stops for benchmark/release review.
