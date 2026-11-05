"""Host-owned target/check identities and explicit rule adoption."""

from specflow.contract_review.common import ReviewError, digest, identity
from specflow.contract_review.sources import select_text

SUPPORT_VERSION = "contract-static-support.v1"


def project_rule_material(adoption):
    """Full frozen text is required; provenance never grants snapshot-tool access."""
    if digest(adoption["body"].encode("utf-8")) != adoption["body_hash"]:
        raise ReviewError("SOURCE_INTEGRITY_FAILED", "冻结项目规则正文已变化。")
    return {
        "adoption_id": adoption["adoption_id"],
        "body_ref": adoption["body_ref"],
        "body": adoption["body"],
        "body_hash": adoption["body_hash"],
        "message_index": 1,
        "disposition": "retained",
    }


def match_scope(scope: dict, target: dict) -> str:
    if target["api_version"] not in scope["api_versions"]:
        return "no_match"
    unresolved = False
    for dimension, field in (("endpoints", "endpoint"), ("source_paths", "source_path")):
        if dimension not in scope:
            continue
        if field not in target:
            unresolved = True
        elif target[field] not in scope[dimension]:
            return "no_match"
    return "scope_unresolved" if unresolved else "match"


def match_effective_scope(expression: dict, target: dict) -> str:
    base = match_scope(expression["base_scope"], target)
    if base != "match":
        return base
    removals = [match_scope(scope, target) for scope in expression["removal_slices"]]
    if "match" in removals:
        return "no_match"
    return "scope_unresolved" if "scope_unresolved" in removals else "match"


def freeze_input(
    request, snapshot: dict, profile: dict, input_id: str, original_request=None
) -> dict:
    raw = request.model_dump(exclude_none=True)
    sources = {item["path"]: item for item in snapshot["files"]}
    targets, checks, adoptions, bindings = [], [], [], []

    def source_ref(path, selector, *, authority=False):
        source = sources.get(path)
        if not source:
            raise ReviewError("INVALID_AUTHORITY_BINDING", "引用不属于所选快照。", 422)
        if authority and not {"contract", "decision_reference"}.intersection(source["roles"]):
            raise ReviewError("INVALID_AUTHORITY_BINDING", "规则引用需要规范或决定参考来源。", 422)
        body = select_text(source["body"], selector)
        return {"source_id": source["source_id"], "selector": selector}, body

    for value in raw["targets"]:
        target = {key: item for key, item in value.items() if key != "checks"}
        target["target_id"] = identity("target")
        if "source_path" in target and target["source_path"] not in sources:
            raise ReviewError("INPUT_SCOPE_CONFLICT", "目标路径不属于所选快照。")
        targets.append(target)
        for check in value["checks"]:
            refs = [
                source_ref(item["path"], item["selector"], authority=True)[0]
                for item in check["rule_selectors"]
            ]
            checks.append(
                {
                    "check_id": identity("check"),
                    "target_id": target["target_id"],
                    "key": check["key"],
                    "behavior": check["behavior"],
                    "rule_source_refs": refs,
                }
            )
    for value in raw["authority_bindings"]:
        ref, body = source_ref(value["path"], value["selector"], authority=True)
        binding = {"authority_binding_id": identity("binding"), **value, "source_ref": ref}
        bindings.append(binding)
        for target in targets:
            outcome = match_scope(value["scope"], target)
            matched = outcome == "match"
            historical = target["api_version"] not in value["scope"]["api_versions"]
            reason = (
                "VERSION_OUT_OF_SCOPE"
                if historical
                else {
                    "match": "EXACT_SCOPE_MATCH",
                    "no_match": "TARGET_OUT_OF_SCOPE",
                    "scope_unresolved": "SCOPE_UNRESOLVED",
                }[outcome]
            )
            adoptions.append(
                {
                    "adoption_id": identity("adopt"),
                    "origin": {
                        "kind": "authority_binding",
                        "authority_binding_id": binding["authority_binding_id"],
                    },
                    "input_revision_id": input_id,
                    "snapshot_id": snapshot["snapshot_id"],
                    "commit_sha": snapshot["commit_sha"],
                    "adopted_ruleset_version": None,
                    "provenance": {"source_ref": ref, "purpose": value["purpose"]},
                    "body_ref": ref,
                    "body_hash": digest(body.encode("utf-8")),
                    "declared_scope": value["scope"],
                    "effective_scope_expression": {
                        "base_scope": value["scope"],
                        "removal_slices": [],
                    },
                    "target_id": target["target_id"],
                    "matched_target": target,
                    "disposition": "adopted"
                    if matched
                    else "historical_only"
                    if historical
                    else "excluded",
                    "reason_code": reason,
                    "reason_text": "同一目标精确匹配。"
                    if matched
                    else "范围不匹配或缺少必要目标维度。",
                    "effect_relation_refs": [],
                }
            )
    value = {
        "input_revision_id": input_id,
        "original_request": original_request
        if original_request is not None
        else request.model_dump(exclude_none=True, exclude_unset=True),
        "snapshot_id": snapshot["snapshot_id"],
        "commit_sha": snapshot["commit_sha"],
        "target_manifest": targets,
        "check_manifest": checks,
        "authority_bindings": bindings,
        "adoption_records": adoptions,
        "adopted_ruleset_version": None,
        "support_matrix_version": SUPPORT_VERSION,
        "resolutions": [],
        "verification_evidence_adoptions": [],
        "execution_profile": profile,
        "profile_hash": digest(profile),
    }
    value["input_hash"] = digest(value)
    return value
