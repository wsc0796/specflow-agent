"""Deterministic report ownership, reference and coverage validation, not semantics."""

from specflow.contract_review.common import canonical, digest
from specflow.contract_review.inputs import match_effective_scope
from specflow.contract_review.protocol import ReportPayload
from specflow.contract_review.sources import select_text
from specflow.contract_review.tool_protocol import covers_selector


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique(values, label):
    encoded = [canonical(value) for value in values]
    require(len(encoded) == len(set(encoded)), f"Duplicate {label}")


def keyed(values, key):
    unique([item[key] for item in values], key)
    return {item[key]: item for item in values}


def question_checks(question, report):
    findings = set(question["finding_ids"])
    for item in report["work_items"]:
        if item["id"] in question["work_item_ids"]:
            findings.update(item["finding_ids"])
    return {
        item["check_id"]
        for item in report["check_results"]
        if findings.intersection(item["finding_ids"])
    }


def source_was_read(reference, reads, body):
    requested = reference["selector"]
    matching = [item["selector"] for item in reads if item["source_id"] == reference["source_id"]]
    return covers_selector(matching, requested, len(body.splitlines()))


def validate_source_refs(values, sources, read_refs):
    unique(values, "source reference")
    for ref in values:
        require(ref["source_id"] in sources, "Source belongs to another input")
        source = sources[ref["source_id"]]
        require(
            digest(source["body"].encode("utf-8")) == source["body_hash"], "Source body damaged"
        )
        select_text(source["body"], ref["selector"])
        require(
            source_was_read(ref, read_refs, source["body"]), "Referenced body was not projected"
        )


def validate_rule_body(adoption, sources, read_refs):
    if adoption.get("origin", {}).get("kind") == "project_decision":
        # Full immutable text is mandatory in each parent/child/review adoption_records.
        require(
            adoption["body_ref"]
            == {"project_decision_id": adoption["origin"]["project_decision_id"]},
            "Project decision body belongs to another origin",
        )
        require(
            digest(adoption["body"].encode("utf-8")) == adoption["body_hash"],
            "Adopted rule body damaged",
        )
        return
    ref = adoption["body_ref"]
    validate_source_refs([ref], sources, read_refs)
    body = select_text(sources[ref["source_id"]]["body"], ref["selector"])
    require(digest(body.encode("utf-8")) == adoption["body_hash"], "Adopted rule body damaged")


def validate_material_refs(values, frozen, sources, read_refs, observations=()):
    unique(values, "material")
    adoptions = keyed(frozen["adoption_records"], "adoption_id")
    for ref in values:
        if ref["kind"] == "source":
            validate_source_refs([ref["source_ref"]], sources, read_refs)
        elif ref["kind"] == "rule":
            require(ref["adoption_id"] in adoptions, "Unknown adoption")
            validate_rule_body(adoptions[ref["adoption_id"]], sources, read_refs)
        else:
            require(ref["observation_id"] in observations, "Unknown accepted observation")


def validate_report(
    value,
    frozen,
    sources,
    read_refs,
    observations=None,
    historical_reports=None,
    projected_evidence_ids=(),
    child_reviews=(),
):
    payload = ReportPayload.model_validate(value).model_dump(exclude_none=True)
    actual_children = keyed(payload["adopted_child_result_refs"], "child_result_ref")
    expected_children = keyed(list(child_reviews), "child_result_ref")
    require(actual_children == expected_children, "Child summary differs from latest parent review")
    if actual_children:
        require(
            frozen.get("execution_profile", {}).get("options", {}).get("delegate", False),
            "Delegation is not enabled",
        )
    observations, historical_reports = observations or {}, historical_reports or {}
    targets = keyed(frozen["target_manifest"], "target_id")
    checks = keyed(frozen["check_manifest"], "check_id")
    adoptions = keyed(frozen["adoption_records"], "adoption_id")
    evidence_adoptions = keyed(frozen["verification_evidence_adoptions"], "evidence_id")
    coverage, results = (
        keyed(payload["coverage"], "target_id"),
        keyed(payload["check_results"], "check_id"),
    )
    uses = keyed(payload["rule_uses"], "adoption_id")
    findings = keyed(payload["findings"], "id")
    questions = keyed(payload["questions"], "id")
    work = keyed(payload["work_items"], "id")
    acceptances = keyed(payload["acceptance_items"], "id")
    typed = {
        "target": targets,
        "finding": findings,
        "question": questions,
        "work_item": work,
        "rule": adoptions,
        "source": sources,
    }
    for resolution in frozen.get("resolutions", []):
        if resolution["answer"]["answer_type"] != "mark_insufficient":
            continue
        question = resolution["question"]
        affected = set(question["target_ids"])
        affected_checks = set(resolution.get("check_ids", question_checks(question, payload)))
        affected_findings = {
            identifier
            for item in results.values()
            if item["check_id"] in affected_checks
            for identifier in item["finding_ids"]
        }
        require(
            not any(
                item["blocking"]
                and item["kind"] == question["kind"]
                and (
                    bool(affected_checks.intersection(question_checks(item, payload)))
                    if affected_checks
                    else item["prompt"] == question["prompt"]
                    and set(item["target_ids"]) == affected
                )
                for item in questions.values()
            ),
            "Insufficient material cannot reopen the same blocking question",
        )
        require(
            all(
                item["readiness"] == "not_ready"
                for item in work.values()
                if affected_findings.intersection(item["finding_ids"])
            ),
            "Insufficient material cannot make related work ready",
        )
        require(
            all(
                item["status"] != "checked"
                for item in results.values()
                if item["check_id"] in affected_checks
            ),
            "Insufficient check must retain a gap",
        )
        require(
            all(
                coverage[target]["status"] != "covered" for target in affected if target in coverage
            ),
            "Insufficient material must retain a coverage gap",
        )
    require(set(coverage) == set(targets), "Coverage must equal frozen targets")
    require(set(results) == set(checks), "Results must equal frozen checks")

    def refs(values, allowed, label):
        unique(values, label)
        require(all(item in allowed for item in values), f"Unknown {label}")

    def source_refs(values):
        validate_source_refs(values, sources, read_refs)

    def materials(values):
        validate_material_refs(values, frozen, sources, read_refs, observations)

    def external_refs(values, target_ids, *, supporting):
        refs(values, evidence_adoptions, "adopted evidence")
        refs(values, projected_evidence_ids, "projected evidence")
        for evidence_id in values:
            binding = evidence_adoptions[evidence_id]
            require(
                binding["adopting_input_revision_id"] == frozen["input_revision_id"],
                "Evidence adoption belongs to another input",
            )
            checks = keyed(binding["target_checks"], "target_id")
            require(
                set(checks) == set(targets), "Evidence applicability must cover current targets"
            )
            if supporting:
                require(
                    all(
                        checks[target_id]["applicability"] == "applicable"
                        for target_id in target_ids
                    ),
                    "External evidence is not applicable to each supported target",
                )

    for identifier, item in uses.items():
        require(identifier in adoptions, "Unknown adoption")
        if item["usage"] == "support":
            require(
                adoptions[identifier]["disposition"] == "adopted", "Unadopted rule used as support"
            )
            adoption = adoptions[identifier]
            validate_rule_body(adoption, sources, read_refs)
            require(adoption["target_id"] in targets, "Rule targets another input")
            require(
                match_effective_scope(
                    adoption["effective_scope_expression"], targets[adoption["target_id"]]
                )
                == "match",
                "Rule effective scope is unresolved or excluded",
            )
    for item in findings.values():
        refs(item["target_ids"], targets, "target")
        refs(item["rule_refs"], adoptions, "adoption")
        refs(item["observation_refs"], observations, "accepted observation")
        unique(item["affected_artifacts"], "artifact role")
        unique(item["labels"], "label")
        source_refs(item["source_refs"])
        external_refs(
            item["verification_evidence_refs"],
            item["target_ids"],
            supporting=item["judgment_status"] in ("supported_deviation", "no_deviation"),
        )
        for relation in item["related_findings"]:
            previous = historical_reports.get(relation["report_revision_id"], {})
            require(relation["finding_id"] in previous, "Unknown historical finding")
        if item["judgment_status"] in ("supported_deviation", "no_deviation"):
            require(
                item["source_refs"] or item["observation_refs"],
                "Affirmative finding needs read evidence",
            )
            for target_id in item["target_ids"]:
                require(
                    any(
                        adoptions[ref]["disposition"] == "adopted"
                        and adoptions[ref]["target_id"] == target_id
                        and uses.get(ref, {}).get("usage") == "support"
                        for ref in item["rule_refs"]
                    ),
                    "No adopted supporting rule for target",
                )
        if item["judgment_status"] in ("needs_decision", "insufficient_evidence"):
            require(item["limitations"], "Gap finding needs an explanation")
    for item in questions.values():
        refs(item["target_ids"], targets, "target")
        refs(item["finding_ids"], findings, "finding")
        refs(item["work_item_ids"], work, "work item")
        refs(item["rule_refs"], adoptions, "adoption")
        unique(item["allowed_answer_types"], "answer type")
        materials(item["evidence_refs"])
    for item in findings.values():
        if item["judgment_status"] == "needs_decision":
            require(
                any(item["id"] in question["finding_ids"] for question in questions.values()),
                "Decision finding lacks a question",
            )
    for identifier, item in results.items():
        refs(item["finding_ids"], findings, "finding")
        refs(item["observation_refs"], observations, "accepted observation")
        source_refs(item["source_refs"])
        for ref in item["finding_ids"]:
            require(
                checks[identifier]["target_id"] in findings[ref]["target_ids"],
                "Check/finding target mismatch",
            )
        if item["status"] == "checked":
            require(
                item["finding_ids"] and (item["source_refs"] or item["observation_refs"]),
                "Checked needs evidence",
            )
            require(not item["missing_information"], "Checked cannot contain an explicit gap")
            require(
                all(
                    findings[ref]["judgment_status"] != "insufficient_evidence"
                    for ref in item["finding_ids"]
                ),
                "Insufficient cannot be checked",
            )
        else:
            require(item["missing_information"], "Gap check needs missing_information")
            require(
                all(
                    findings[ref]["judgment_status"] != "no_deviation"
                    for ref in item["finding_ids"]
                ),
                "Gap cannot support no_deviation",
            )
            if item["status"] == "not_checked":
                require(
                    not item["source_refs"] and not item["observation_refs"],
                    "Unchecked evidence claim",
                )
    for item in findings.values():
        if item["judgment_status"] == "insufficient_evidence":
            require(
                any(
                    result["status"] != "checked" and item["id"] in result["finding_ids"]
                    for result in results.values()
                ),
                "Insufficient finding needs a gap check",
            )
    for identifier, item in coverage.items():
        source_refs(item["source_refs"])
        if item["status"] == "covered":
            require(not item["missing_information"], "Covered target contains a gap")
            require(
                all(
                    results[key]["status"] == "checked"
                    for key, check in checks.items()
                    if check["target_id"] == identifier
                ),
                "Covered target has unchecked behavior",
            )
        else:
            require(item["missing_information"], "Coverage gap lacks explanation")
            if item["status"] == "not_read":
                require(not item["source_refs"], "Unread target claims read references")
    for item in work.values():
        refs(item["finding_ids"], findings, "finding")
        refs(item["target_ids"], targets, "target")
        refs(item["rule_refs"], adoptions, "adoption")
        refs(item["depends_on"], work, "work item")
        refs(item["acceptance_ids"], acceptances, "acceptance")
        source_refs(item["source_refs"])
        require(item["id"] not in item["depends_on"], "Self dependency")
        if item["handling_intent"]["kind"] not in ("obtain_evidence", "resolve_rule"):
            require(
                item["rule_refs"] and item["source_refs"], "Supported change needs rule and source"
            )
        for blocker in item["blockers"]:
            unique(blocker["refs"], "blocker reference")
            for ref in blocker["refs"]:
                require(ref["id"] in typed[ref["kind"]], "Unknown typed blocker reference")
        for ref in item["acceptance_ids"]:
            require(acceptances[ref]["work_item_id"] == item["id"], "Acceptance ownership mismatch")
    visited, visiting = set(), set()

    def visit(identifier):
        require(identifier not in visiting, "Cyclic work dependencies")
        if identifier in visited:
            return
        visiting.add(identifier)
        for dependency in work[identifier]["depends_on"]:
            visit(dependency)
        visiting.remove(identifier)
        visited.add(identifier)

    for identifier in work:
        visit(identifier)
    for item in acceptances.values():
        require(item["work_item_id"] in work, "Acceptance has no work item")
        require(
            item["id"] in work[item["work_item_id"]]["acceptance_ids"], "Missing reverse acceptance"
        )
        refs(item["finding_ids"], findings, "finding")
        refs(item["target_ids"], targets, "target")
        refs(item["rule_refs"], adoptions, "adoption")
        source_refs(item["source_refs"])
        external_refs(item["evidence_refs"], item["target_ids"], supporting=True)
    mapping = {
        "not_checked": "unchecked",
        "unsupported": "unsupported_structure",
        "evidence_missing": "missing_evidence",
        "partial": "target_partial",
        "not_read": "target_not_read",
    }
    gap_checks = sorted(key for key, item in results.items() if item["status"] != "checked")
    gap_targets = sorted(key for key, item in coverage.items() if item["status"] != "covered")
    reasons = {mapping[results[key]["status"]] for key in gap_checks}
    reasons.update(mapping[coverage[key]["status"]] for key in gap_targets)
    return payload, {
        "level": "degraded" if gap_checks or gap_targets else "complete",
        "gap_check_ids": gap_checks,
        "gap_target_ids": gap_targets,
        "reason_codes": sorted(reasons),
    }
