"""Exact-scope and three-valued remaining-authority boundaries."""

import pytest

from specflow.contract_review.inputs import freeze_input, match_effective_scope, match_scope
from specflow.contract_review.schemas import CreateReview, Scope

ENDPOINT = {"method": "POST", "path": "/exports"}


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ({"api_version": "v1", "endpoint": ENDPOINT}, "no_match"),
        ({"api_version": "v2", "endpoint": ENDPOINT}, "scope_unresolved"),
        ({"api_version": "v2", "source_path": "docs/a.md"}, "scope_unresolved"),
        ({"api_version": "v2", "endpoint": ENDPOINT, "source_path": "docs/a.md"}, "no_match"),
        ({"api_version": "v2", "endpoint": ENDPOINT, "source_path": "docs/b.md"}, "match"),
    ],
)
def test_partial_removal_does_not_treat_unknown_as_false(target, expected):
    expression = {
        "base_scope": {"api_versions": ["v2"], "endpoints": [ENDPOINT]},
        "removal_slices": [{"api_versions": ["v2"], "source_paths": ["docs/a.md"]}],
    }
    assert match_effective_scope(expression, target) == expected


def test_known_removal_wins_even_if_another_slice_is_unresolved():
    expression = {
        "base_scope": {"api_versions": ["v2"], "endpoints": [ENDPOINT]},
        "removal_slices": [
            {"api_versions": ["v2"], "source_paths": ["docs/a.md"]},
            {"api_versions": ["v2"], "endpoints": [ENDPOINT]},
        ],
    }
    assert (
        match_effective_scope(expression, {"api_version": "v2", "endpoint": ENDPOINT}) == "no_match"
    )


def test_scope_never_combines_dimensions_from_two_targets():
    scope = {"api_versions": ["v2"], "endpoints": [ENDPOINT], "source_paths": ["docs/a.md"]}
    first = {"api_version": "v2", "endpoint": ENDPOINT, "source_path": "src/api.py"}
    second = {
        "api_version": "v2",
        "endpoint": {"method": "GET", "path": "/other"},
        "source_path": "docs/a.md",
    }
    assert match_scope(scope, first) == match_scope(scope, second) == "no_match"


def test_scope_normalizes_only_explicit_sets_and_method_case():
    value = Scope.model_validate(
        {
            "api_versions": ["v2", "v2"],
            "endpoints": [
                {"method": "post", "path": "/exports/"},
                {"method": "POST", "path": "/exports/"},
            ],
            "source_paths": ["docs/A.md", "docs/A.md"],
        }
    )
    assert value.model_dump(exclude_none=True) == {
        "api_versions": ["v2"],
        "endpoints": [{"method": "POST", "path": "/exports/"}],
        "source_paths": ["docs/A.md"],
    }
    assert (
        match_scope(
            value.model_dump(exclude_none=True),
            {"api_version": "v2", "endpoint": ENDPOINT, "source_path": "docs/A.md"},
        )
        == "no_match"
    )


@pytest.mark.parametrize("paths", [[], None])
def test_empty_or_null_optional_dimension_is_not_all(paths):
    with pytest.raises(ValueError):
        Scope.model_validate(
            {"api_versions": ["v2"], "endpoints": [ENDPOINT], "source_paths": paths}
        )


def test_historical_and_excluded_rules_keep_different_reasons(review_client):
    _, domain, body = review_client
    body["authority_bindings"].append(
        {
            **body["authority_bindings"][0],
            "scope": {"api_versions": ["v1"], "endpoints": [ENDPOINT]},
        }
    )
    body["authority_bindings"].append(
        {
            **body["authority_bindings"][0],
            "scope": {"api_versions": ["v2"], "source_paths": ["not-selected.md"]},
        }
    )
    request = CreateReview.model_validate(body)
    with domain.store.read() as conn:
        path = domain.store.row(
            conn, "SELECT repository_path FROM projects WHERE id=:id", id=body["project_id"]
        )["repository_path"]
    frozen = freeze_input(
        request,
        domain.snapshot_reader.prepare(path, request.source),
        next(iter(domain.profiles.values())),
        "ir-test",
    )
    statuses = {(item["disposition"], item["reason_code"]) for item in frozen["adoption_records"]}
    assert ("adopted", "EXACT_SCOPE_MATCH") in statuses
    assert ("historical_only", "VERSION_OUT_OF_SCOPE") in statuses
    assert ("excluded", "TARGET_OUT_OF_SCOPE") in statuses
