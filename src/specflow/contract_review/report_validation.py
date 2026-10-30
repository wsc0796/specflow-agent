"""Deterministic report ownership, reference and coverage validation, not semantics."""

from specflow.contract_review.common import canonical, digest
from specflow.contract_review.protocol import ReportPayload
from specflow.contract_review.sources import select_text


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique(values, label):
    encoded = [canonical(value) for value in values]
    require(len(encoded) == len(set(encoded)), f"Duplicate {label}")


def keyed(values, key):
    unique([item[key] for item in values], key)
    return {item[key]: item for item in values}


def source_was_read(reference, reads, body):
    requested = reference["selector"]
    matching = [item["selector"] for item in reads if item["source_id"] == reference["source_id"]]
    if any(item["kind"] == "full" for item in matching):
        return True
    if requested["kind"] == "json_pointer":
        return any(item == requested for item in matching)
    start, end = (
        (1, len(body.splitlines()))
        if requested["kind"] == "full"
        else (requested["start_line"], requested["end_line"])
    )
    intervals = sorted(
        (item["start_line"], item["end_line"]) for item in matching if item["kind"] == "lines"
    )
    next_line = start
    for lower, upper in intervals:
        if lower <= next_line <= upper:
            next_line = upper + 1
    return next_line > end


def validate_report(value, frozen, sources, read_refs, observations=None, historical_reports=None):
    payload = ReportPayload.model_validate(value).model_dump(exclude_none=True)
    observations, historical_reports = observations or {}, historical_reports or {}
    targets = keyed(frozen["target_manifest"], "target_id")
    checks = keyed(frozen["check_manifest"], "check_id")
    adoptions = keyed(frozen["adoption_records"], "adoption_id")
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
    require(set(coverage) == set(targets), "Coverage must equal frozen targets")
    require(set(results) == set(checks), "Results must equal frozen checks")

    def refs(values, allowed, label):
        unique(values, label)
        require(all(item in allowed for item in values), f"Unknown {label}")

    def source_refs(values, *, read=True):
        unique(values, "source reference")
        for ref in values:
            require(ref["source_id"] in sources, "Source belongs to another input")
            source = sources[ref["source_id"]]
            require(
                digest(source["body"].encode("utf-8")) == source["body_hash"], "Source body damaged"
            )
            select_text(source["body"], ref["selector"])
            if read:
                require(
                    source_was_read(ref, read_refs, source["body"]),
                    "Referenced body was not projected",
                )

    def materials(values):
        unique(values, "material")
        for ref in values:
            if ref["kind"] == "source":
                source_refs([ref["source_ref"]])
            elif ref["kind"] == "rule":
                refs([ref["adoption_id"]], adoptions, "adoption")
            else:
                refs([ref["observation_id"]], observations, "accepted observation")

    for identifier, item in uses.items():
        require(identifier in adoptions, "Unknown adoption")
        if item["usage"] == "support":
            require(
                adoptions[identifier]["disposition"] == "adopted", "Unadopted rule used as support"
            )
    for item in findings.values():
        refs(item["target_ids"], targets, "target")
        refs(item["rule_refs"], adoptions, "adoption")
        refs(item["observation_refs"], observations, "accepted observation")
        unique(item["affected_artifacts"], "artifact role")
        unique(item["labels"], "label")
        source_refs(item["source_refs"])
        # External adoption is wired in TASK-03; no undeclared evidence can pass.
        refs(
            item["verification_evidence_refs"],
            {entry["evidence_id"] for entry in frozen["verification_evidence_adoptions"]},
            "evidence",
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
        refs(
            item["evidence_refs"],
            {entry["evidence_id"] for entry in frozen["verification_evidence_adoptions"]},
            "evidence",
        )
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
