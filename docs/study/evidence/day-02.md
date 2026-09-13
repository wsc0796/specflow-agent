yao# Day 02 Evidence Card

- Status: COMPLETE
- Date: 2026-09-07
- Roadmap: V5.3.1 Minimal Observability Patch, Day 2
- Study mode: REVIEW

> Predictions are frozen before execution. Mechanical command execution and
> result collection may be performed by Codex; interpretation, trade-offs, and
> closed-note explanations must come from the learner.

> Route adoption: V5.3.1 replaced V5.3 on 2026-09-07. Its Minimal
> Observability changes begin at Day 22 and do not retroactively complete or
> replace the current Day 2 experiments.

## Experiment S1 — Sampling temperature

### Engineering question

With the Provider, model, prompt, evidence, output limit, and conversation state
held constant, how does changing `temperature` affect decision-level consistency,
and does consistency establish correctness?

### Frozen conditions

| Condition | Temperature | Repetitions |
| --- | ---: | ---: |
| S1-L | 0.0 | 3 |
| S1-H | 1.2 | 3 |

Decision-level variation will be assessed by changes to the highest-priority
risk, the selected risk set, and unsupported claims. Wording-only differences
do not count as decision changes.

### Learner prediction — frozen before execution

> `temperature = 0` will produce more consistent engineering conclusions, and
> this consistency can prove the answer is more correct because a lower value
> makes the answer-choice distributions closer and therefore more reliable.

### Execution preflight

- Repository: `D:/Documents/ChatGPT/一个月冲刺/specflow-agent`
- Branch: `codex/t072-no-evidence-fail-closed`
- HEAD: `c0721ba`
- `SPECFLOW_LLM_BASE_URL`: not configured in the current process
- `SPECFLOW_LLM_API_KEY`: not configured in the current process
- `SPECFLOW_LLM_MODEL`: not configured in the current process
- Mock substitution: forbidden for sampling and semantic-quality claims

Resumption on 2026-09-07: the user authorized use of an existing funded
`DEEPSEEK_API_KEY`. The key is available through the process environment and
will be mapped into SpecFlow configuration without printing or persisting it.

### Raw results

Initial execution through the current SpecFlow Provider adapter used the
DeepSeek V4 default thinking mode: 1/6 calls returned usable final content and
5/6 ended as `LLMResponseError: invalid response structure`.

Diagnostic evidence for a failing call:

- HTTP status: 200
- `finish_reason`: `length`
- `content`: empty
- `reasoning_content`: 932 characters
- all 512 completion tokens were reasoning tokens

Root cause: the default thinking mode exhausted `max_tokens=512` before final
content. The adapter then rejected the empty content. This attempt is retained
at `artifacts/day02-llm-lab/sampling-temperature.json` and is excluded from the
temperature comparison.

A minimal direct-API probe with `thinking=disabled` returned non-empty content
and `finish_reason=stop`. The controlled comparison was then rerun without
automatic retry in alternating order `0.0, 1.2, 0.0, 1.2, 0.0, 1.2`.

| Run | Temperature | Result | Output tokens | Cache hit / miss input tokens |
| --- | ---: | --- | ---: | ---: |
| S1-valid-1 | 0.0 | success / stop | 294 | 0 / 156 |
| S1-valid-2 | 1.2 | success / stop | 304 | 128 / 28 |
| S1-valid-3 | 0.0 | success / stop | 306 | 128 / 28 |
| S1-valid-4 | 1.2 | success / stop | 255 | 128 / 28 |
| S1-valid-5 | 0.0 | success / stop | 265 | 128 / 28 |
| S1-valid-6 | 1.2 | success / stop | 261 | 128 / 28 |

- Successful comparison calls: 6/6
- Model: `deepseek-v4-flash`
- System fingerprint: `a26a7955944dc5c60445bff77fac9c8e`
- Total prompt tokens: 936, including 640 cache-hit and 296 cache-miss tokens
- Total completion tokens: 1685
- Estimated valid-run cost at the observed peak price: `$0.00236`
- Raw artifact: `artifacts/day02-llm-lab/sampling-temperature-thinking-disabled.json`

### Learner verification and interpretation

- Learner interpretation draft: `temperature=0.0` is more stable and that
  stability proves correctness; the learner could not yet identify a concrete
  evidence item.
- Review status: needs revision. Repeated agreement is evidence of stability,
  not correctness. Correctness additionally requires mapping claims to the
  supplied facts or another explicit acceptance reference.
- Corrected learner interpretation: all three `temperature=0.0` runs kept the
  same top risk and the same three risk themes, which proves consistency of
  ranking and themes only. Correctness still requires mapping every conclusion
  back to the supplied facts.
- Interpretation status: accepted. Sampling trade-off is pending.
- Learner trade-off draft: choose `temperature=0.0` for greater accuracy and
  uniformity; the stated cost is a significant reduction in task success and
  adaptability for reasoning, exploration, correction, and collaboration.
- Trade-off review: needs revision. The experiment supports greater consistency,
  not greater accuracy, and contains no success-rate measurement. Reduced
  diversity or candidate coverage is a supported risk hypothesis; a significant
  success-rate reduction is not established.
- Corrected learner trade-off: choose `temperature=0.0` for more consistent,
  reproducible, regression-friendly, and auditable output. The cost is reduced
  output diversity and a risk of missing alternatives; any task-success impact
  still requires a separate experiment.
- Sampling experiment status: accepted.

## Experiment C1 — Context/evidence position

### Engineering question

When the exact same trusted source, untrusted conflicting text, neutral context,
and final question are held constant, does the position of the trusted source
change whether the model uses the correct fact and provenance?

### Frozen conditions

- Provider/model: DeepSeek `deepseek-v4-flash`
- `thinking=disabled`, `temperature=0.0`, `max_tokens=256`
- Three independent calls per position; no automatic retry
- Same three context blocks; only their order changes
- Trusted fact: `LLMRequest.temperature` defaults to `0.0` and accepts `0..2`
  in `src/specflow/llm/models.py`
- Untrusted conflict: an instruction-like repository note claims default `1.0`
  and range `0..1`

| Condition | Context block order | Repetitions |
| --- | --- | ---: |
| C1 | trusted → neutral → untrusted → question | 3 |
| C2 | neutral → trusted → untrusted → question | 3 |
| C3 | neutral → untrusted → trusted → question | 3 |

### Learner prediction — frozen before execution

> C1, with trusted evidence at the beginning, will be used correctly most
> often. Position cannot override trust level because the evidence source is the
> same.

### Raw results

The nine calls ran in alternating order `C1, C2, C3` for three rounds without
automatic retry.

| Condition | Successful calls | Correct default/range present | Trusted source present | Conflict identified |
| --- | ---: | ---: | ---: | ---: |
| C1 | 3/3 | 3/3 | 3/3 | 3/3 |
| C2 | 3/3 | 3/3 | 3/3 | 3/3 |
| C3 | 3/3 | 3/3 | 3/3 | 3/3 |

- Model: `deepseek-v4-flash`
- System fingerprint: `a26a7955944dc5c60445bff77fac9c8e`
- Total prompt tokens: 2160, including 768 cache-hit and 1392 cache-miss tokens
- Total completion tokens: 707
- Estimated cost at the observed peak price: `$0.00156`
- Raw artifact: `artifacts/day02-llm-lab/context-evidence-position.json`

### Learner verification and interpretation

- Learner interpretation draft: the result proves that trusted evidence at the
  beginning has no effect in this case and cannot prove that position never
  matters; the learner did not yet understand the role of trusted versus
  untrusted source labels.
- Review status: needs revision. The result shows only that no position-related
  difference was observed under this short, strongly labeled, single-model
  sample. Trust labels tell the model which source may support facts and which
  repository text must remain untrusted data; they do not create a deterministic
  security boundary.
- Second learner draft: evidence at the beginning has no effect; the labels are
  Prompt trust cues; there is no evidence for a universal position claim.
- Second review: still needs revision. State the observed tie rather than a
  no-effect claim, explain what the labels direct the model to do, and name the
  missing coverage: other models, longer/noisier contexts, and more repetitions.
- Corrected learner interpretation: all three positions achieved 3/3, so no
  position difference was observed in this sample. Trusted source content may
  support facts; untrusted repository text remains data and its embedded
  “ignore the rules” instruction must not execute. The experiment covered only
  one model, one short Prompt, and three calls per position, not long Context,
  weak labels, or heavy distractors.
- Context interpretation status: accepted. Trade-off is pending.
- Learner trade-off draft: prioritize source trust so conclusions are usually
  better; the limitation is that the Agent may not follow the intended rule.
- Trade-off review: direction accepted but the mechanisms need separation.
  Prompt labels improve the chance that the model uses the intended source but
  can be ignored; deterministic path, permission, and DLP controls constrain
  what data reaches or leaves the model and cannot be replaced by labels.
- Corrected learner trade-off: source-role labels help the model distinguish
  evidence, but the model may ignore them. Path and permission controls decide
  what can be read, while DLP also checks or redacts sensitive content before it
  is sent or persisted.
- Context trade-off status: accepted.

## Experiment O1 — Structured Output

### Live comparison — Prompt-only vs Provider JSON mode

#### Frozen conditions

- Provider/model: DeepSeek `deepseek-v4-flash`
- `thinking=disabled`, `temperature=1.0`, `max_tokens=256`
- Identical Prompt and evidence; three independent calls per condition
- O-Live-A: Prompt requests strict JSON; `response_format` omitted
- O-Live-B: Prompt requests strict JSON;
  `response_format={"type":"json_object"}`
- Deterministic checks: `json.loads` followed by a strict local Pydantic Schema
- No automatic retry

#### Learner prediction — frozen before execution

> O-Live-B will have the higher JSON parse success rate. Provider JSON mode can
> constrain the JSON format, but it cannot guarantee field/type contracts or
> business correctness.

#### Raw results

The six calls ran in alternating order `O-Live-A, O-Live-B` for three rounds
without automatic retry.

| Condition | Successful calls | JSON parse success | Strict local Schema success | Prompt / output tokens |
| --- | ---: | ---: | ---: | ---: |
| O-Live-A: Prompt-only | 3/3 | 3/3 | 3/3 | 369 / 439 |
| O-Live-B: Provider JSON mode | 3/3 | 3/3 | 3/3 | 429 / 307 |

- Model: `deepseek-v4-flash`
- System fingerprint: `a26a7955944dc5c60445bff77fac9c8e`
- Total prompt tokens: 798, including 256 cache-hit and 542 cache-miss tokens
- Total completion tokens: 746
- Estimated cost at the observed peak price: `$0.00123`
- Raw artifact: `artifacts/day02-llm-lab/response-format-comparison.json`

#### Learner verification and interpretation

- Mechanical observation: both conditions achieved 3/3 JSON parse and 3/3
  strict local Schema success in this sample.
- Prediction review: the predicted higher parse success for O-Live-B was not
  observed; the result was a tie. This six-call sample does not prove that the
  two controls are equivalent or that either guarantees business correctness.
- Learner interpretation draft: JSON-object mode had no effect on the result;
  the experiment had no controlled variable; choose O-Live-B and retain Schema
  and business validation.
- Review status: needs revision. Model, Prompt, evidence, temperature, thinking
  mode, and output budget were fixed; `response_format` was the single changed
  variable. The 3/3 tie means only that no difference was observed in this small
  sample. Production handling must still parse JSON before Schema and
  business/evidence validation.
- Corrected learner interpretation: in this six-call sample both conditions
  achieved 3/3 JSON parsing and strict Schema validation. This does not prove
  equivalence because the sample is small and the controls do not validate
  semantic correctness, business consistency, reasoning depth, result quality,
  or evidence completeness. Production should use Provider JSON mode while
  retaining JSON parsing, Schema validation, and business/evidence validation.
- Structured Output interpretation status: accepted.

### Fault O1 — JSON-valid but Schema-invalid payload

```json
{
  "summary": "",
  "unexpected_field": "extra"
}
```

The target contract is `DesignPayload`: `summary` has `min_length=1` and the
strict payload base rejects unknown fields.

### Learner prediction — frozen before execution

> JSON parsing will succeed, Schema validation will fail, and SpecFlow will
> return a degraded result.

### Raw results

Executed locally through the current repository code without changing product
files:

| Stage | Observed result |
| --- | --- |
| `json.loads` | Success; produced an object with `summary` and `unexpected_field` |
| `DesignPayload.model_validate` | Failed with `string_too_short` at `summary` and `extra_forbidden` at `unexpected_field` |
| `AgentRunner.execute` | `success=false`, `degraded=true`, `schema_validated=false`, `error_code=SCHEMA_VALIDATION_FAILED` |

The deterministic Mock was used only to inject the exact fault text into the
real parser/Schema boundary. It is not evidence about live-model quality.

### Learner verification and interpretation

- Initial explanation correctly separated JSON parseability from usability but
  conflated Schema validity with business correctness and attributed degradation
  to performance.
- Corrected learner explanation: Schema validation guarantees that fields,
  types, and constraints conform to the declared contract.
- Degradation rationale: prevent unvalidated data from reaching downstream
  Agents that might continue from a broken contract or record false success.
- Interpretation status: accepted.

### Fault O2 — Schema-valid but unverified claim

```json
{
  "summary": "全部测试已经通过"
}
```

No test command is executed before this payload is injected.

### Learner prediction — frozen before execution

> The current runtime will degrade. The payload cannot prove that all tests
> passed because the business result has not been verified and no tests were
> run.

### Raw results

| Stage | Observed result |
| --- | --- |
| `json.loads` | Success |
| `DesignPayload.model_validate` | Success; default empty collections were populated |
| `AgentRunner.execute` | `success=true`, `schema_validated=true`; the unverified `summary` was accepted |

No test command or evidence-validity check was performed before the successful
result. The Mock was used only to inject the exact deterministic payload; this
does not establish live-model quality.

### Learner verification and interpretation

- Prediction review: partially falsified. The learner correctly stated that the
  payload cannot prove test success, but incorrectly predicted runtime
  degradation. The current boundary accepts it because JSON and Schema checks
  pass and `AgentRunner` performs no factual test-evidence validation.
- Corrected learner interpretation: JSON parsing checks whether the result can
  be parsed as valid JSON; Schema validation checks whether fields, types, and
  constraints conform to the declared contract; factual support belongs to the
  business/evidence validation boundary.
- Interpretation status: accepted.

### Learner trade-off

> Keep factual validation in a separate business/evidence validation Module
> because this lowers coupling. The cost is additional tests and a longer call
> chain.

- Trade-off status: accepted.
- Local-slice boundary: JSON parsing, Schema validation, factual validation,
  failure behavior, and seam placement were demonstrated. Prompt-only versus
  provider `response_format` behavior still requires a real model.

### Fault O3 — Markdown-fenced JSON

The injected provider content will be:

````text
```json
{"summary": "合法内容"}
```
````

The JSON object inside the fences is valid and Schema-compatible. The learner
must predict whether the current runtime strips the fences, repairs the text,
retries, or returns a classified failure before execution.

### Learner prediction — frozen before execution

> The final result will be `degraded`, but the runtime will first strip the
> Markdown fence, attempt repair, and retry. The failure is attributed to an
> incorrect business result.

### Raw results

| Observation | Result |
| --- | --- |
| `json.loads(full_response)` | `JSONDecodeError` at line 1, column 1 |
| Manually extracted inner object | JSON parse success and `DesignPayload` validation success |
| LLM call count | 1; no retry occurred |
| `AgentRunner.execute` | `success=false`, `degraded=true`, `schema_validated=false`, `error_code=JSON_PARSE_FAILED` |

### Learner verification and interpretation

- Prediction review: partially falsified. `degraded` was correct, but the current
  runtime did not strip the fence, repair the response, or retry.
- Failure location: JSON parsing of the complete provider response. Schema and
  business validation were not reached; the inner business content was not the
  cause of this failure.
- Learner explanation draft: the failure is in the JSON validation layer because
  the format is invalid.
- Explanation review: correct but incomplete; the learner still needs to connect
  whole-response parsing, downstream stages not being reached, and the retry
  scope.
- Corrected learner explanation: the Provider call itself did not fail; the
  returned content failed JSON-format parsing, so Schema and business validation
  were never executed. Provider-call retry therefore did not apply.
- Explanation status: accepted.

## Five failure explanations

1. Sampling drift — completed: higher-temperature samples varied more in risk
   themes and readability, while lower-temperature samples retained the same
   ranking and themes in this run set.
2. Stable but wrong — completed: repeated agreement measures consistency, not
   correctness; claims still require mapping to input facts or acceptance
   evidence.
3. Evidence present but not effectively used — completed through C1: merely
   including evidence does not establish a universal position rule; source-role
   labels help the model separate authoritative facts from untrusted repository
   instructions, but broader Context stress evidence is still required.
4. JSON parse failure — completed through O3: the whole provider response must
   be valid JSON; a post-response parse error occurs before Schema/business
   validation and is outside the current Provider-call retry scope.
5. JSON-valid but contract or semantic failure — completed through O1/O2:
   parseability does not prove contract validity, and contract validity does not
   prove factual correctness.

## Closed-note acceptance

All three experiments and all five learner-owned failure explanations are
complete. One closed-note end-to-end teach-back remains before Day 2 can close.

### First closed-note attempt

| Item | Assessment |
| --- | --- |
| Sampling consistency vs correctness | Passed |
| Prompt trust labels vs deterministic controls | Partial; deterministic controls do not rely on model compliance |
| Provider JSON mode boundary | Partial; guarantees JSON syntax, not the full Schema structure |
| JSON → Schema → business/evidence validation | Not understood |
| Degraded-state purpose | Passed |
| Thinking-token exhaustion failure location | Failed; attributed to business-test layer |

Remediation is required for the three validation layers and the Provider
response/Token-budget failure location.

### Closed-note remediation 1 — validation layers

- A non-JSON text fails at JSON parsing.
- A JSON object with an empty required field fails at Schema validation.
- A JSON- and Schema-valid claim that tests passed without test evidence fails
  at business/evidence validation.
- Learner result: 3/3 correct; remediation passed.

### Closed-note remediation 2 — thinking-token exhaustion

- Observed response: HTTP 200, `finish_reason=length`, 512 reasoning tokens,
  and empty final `content`.
- Learner located the first failure at Provider response normalization/output
  completeness because non-empty content is required.
- JSON parsing, Schema validation, and business/evidence validation were not
  reached.
- Learner result: remediation passed.

### Final closed-note teach-back

- First unscaffolded answer correctly stated JSON parsing, Schema field/type
  contract validation, business/test-result verification, and degraded failure
  handling.
- Missing: sampling, Context trust controls, Provider JSON mode, and Provider
  response completeness before JSON parsing.
- Learner supplement: temperature controls generation determinism and format
  compliance; Context labels and deterministic controls govern source trust;
  Provider JSON mode constrains JSON; empty final content fails at Provider
  response normalization.
- Reviewer correction: temperature changes sampling distribution and observed
  consistency, not guaranteed determinism or format compliance. Context labels
  are probabilistic source-role cues, while deterministic controls enforce data
  access/redaction. Provider JSON mode targets JSON syntax, not Schema or
  business correctness.
- Pre-JSON supplement status: accepted with the reviewer correction above.
- Remaining check: explain that the current `AgentRunner` degraded envelope has
  `success=false`, is rejected before Handoff, and stops downstream execution.
- Learner final check: degradation is already completed as a controlled failure;
  because the output was not validated, it is not forwarded to downstream
  Agents as an answer.
- Closed-note status: passed after focused remediation.

## Day 2 completion summary

- Live calls: 21/21 planned calls recorded successfully across the three groups.
- Sampling: interpretation and trade-off accepted; consistency was separated
  from correctness.
- Context: interpretation and trade-off accepted; Prompt trust labels were
  separated from deterministic path, permission, and DLP controls.
- Structured Output: Provider JSON mode, JSON parsing, Schema validation,
  business/evidence validation, Provider response normalization, and degraded
  failure semantics were explained.
- Failure explanations: 5/5 complete.
- Product changes: none.
- Remaining limit: the small, single-model experiment set does not establish a
  universal model-quality, position-effect, or production success-rate claim.
