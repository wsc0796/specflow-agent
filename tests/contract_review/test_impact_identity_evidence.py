"""Identity evidence excludes query echoes and preserves complete path tokens."""

import pytest

from specflow.contract_review.common import digest
from specflow.contract_review.impact_runner import ImpactRunner


def case(body, *, observation=None, rule_body=None):
    runner = object.__new__(ImpactRunner)
    ref = dict(source_id="src_own", selector=dict(kind="full"))
    runner.sources = {
        "src_own": dict(
            source_id="src_own",
            path="docs/api.md",
            roles=["documentation"],
            body=body,
            body_hash=digest(body.encode()),
        )
    }
    runner.frozen = dict(change_request="核对本次接口影响，未提供额外版本或接口事实")
    runner.reads, runner.seen, runner.observations = [ref], set(), {}
    if rule_body:
        runner.sources["src_rule"] = dict(
            source_id="src_rule",
            path="contracts/v2.json",
            roles=["contract"],
            body=rule_body,
            body_hash=digest(rule_body.encode()),
        )
        runner.reads.append(dict(source_id="src_rule", selector=dict(kind="full")))
    if observation:
        runner.observations["iobs_query"] = observation
        runner.seen.add("iobs_query")
    raw = dict(
        schema_version="contract-impact-action.v1",
        action="submit_candidates",
        reason=dict(gap="核对依据", expected_information="合法身份", evidence_refs=[]),
        candidates=[
            dict(
                local_key="candidate",
                source_path="docs/api.md",
                artifact_role="documentation",
                api_version="v2",
                endpoint=dict(method="POST", path="/exports"),
                relation="observed",
                rationale="受控合同",
                suggested_checks=[dict(key="response_field", behavior="核对字段")],
                source_refs=[ref],
                observation_refs=["iobs_query"] if observation else [],
                unknowns=[],
            )
        ],
        unresolved=[],
    )
    return runner, raw


def test_empty_search_query_echo_is_not_an_identity_fact():
    observation = dict(
        body=dict(query="POST /exports", source_ids=["src_own"], matches=[]), source_refs=[]
    )
    runner, raw = case("API v2 POST /other", observation=observation)
    with pytest.raises(ValueError, match="Endpoint identity"):
        runner.validate(raw)


@pytest.mark.parametrize("suffix", ["-v2", ".json", ":batch"])
def test_path_suffix_is_not_silently_removed(suffix):
    runner, raw = case("API v2 POST /exports" + suffix)
    with pytest.raises(ValueError, match="Endpoint identity"):
        runner.validate(raw)


@pytest.mark.parametrize("body", ['API v2 POST "/exports"', "API v2 POST /exports"])
def test_exact_path_tokens_remain_supported(body):
    runner, raw = case(body)
    assert runner.validate(raw)["candidates"][0]["endpoint"]["path"] == "/exports"


def test_observation_support_comes_from_real_projected_source_fragments():
    observation = dict(
        body=dict(query="untrusted echo", matches=[]),
        source_refs=[dict(source_id="src_rule", selector=dict(kind="full"))],
    )
    runner, raw = case(
        "API v2 related material", observation=observation, rule_body='API v2 POST "/exports"'
    )
    assert runner.validate(raw)["candidates"][0]["endpoint"]["path"] == "/exports"
