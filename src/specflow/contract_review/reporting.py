"""Markdown is a disposable projection of the authoritative report and input."""

import html
import json
import re


def escaped(value):
    text = html.escape(str(value), quote=False)
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", lambda match: f"\\u{ord(match[0]):04x}", text)
    return re.sub(r"([\\`*_{}\[\]()#+.!|\-])", r"\\\1", text).replace("\n", "  \n")


def json_block(value):
    body = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
    fence = "`" * max(3, max((len(x) + 1 for x in re.findall(r"`+", body)), default=3))
    return f"{fence}json\n{body}\n{fence}"


def render_report(report, frozen):
    """Keep complete fields, including long text and three-valued evidence states."""
    payload = report["payload"]
    review_id, job_id = report["review_id"], report["job_id"]
    lines = [
        "# 契约审查报告",
        "",
        "本报告是静态审查交付。ready 表示信息可交接；NOT_RUN 表示本系统尚未执行该业务核验。",
        "",
    ]

    def section(title):
        lines.extend(["## " + title, ""])

    def field(label, value):
        lines.extend(
            [
                "**" + label + "**",
                "",
                json_block(value)
                if isinstance(value, (dict, list))
                else escaped("未指定" if value is None else value),
                "",
            ]
        )

    def table(headers, rows):
        def cell(value):
            return escaped(value).replace("  \n", "<br>")

        lines.extend(
            ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
        )
        lines.extend("| " + " | ".join(cell(value) for value in row) + " |" for row in rows)
        lines.append("")

    section("报告与输入身份")
    field(
        "冻结身份",
        {
            key: report[key]
            for key in (
                "schema_version",
                "review_id",
                "input_revision_id",
                "job_id",
                "report_revision_id",
                "snapshot_id",
                "commit_sha",
                "target_api_version",
                "adopted_ruleset_version",
                "verification_mode",
                "execution_mode",
                "created_at",
            )
        },
    )
    field("请求", frozen["original_request"]["request"])
    field("目标清单", frozen["target_manifest"])
    field("选定材料与版本", frozen["original_request"]["source"])
    field("来源绑定与片段身份", frozen["authority_bindings"])
    if "revision_change" in frozen:
        field("本次修订声明与排除理由", frozen["revision_change"])
    if "resolution_adoptions" in frozen:
        field("旧答案采用与排除", frozen["resolution_adoptions"])
    profile = frozen["execution_profile"]
    field(
        "冻结执行配置",
        {
            "profile_hash": frozen["profile_hash"],
            **{
                key: profile[key]
                for key in ("profile_id", "engine_version", "model", "execution_mode", "options")
            },
        },
    )
    section("结论与覆盖质量")
    field("摘要", payload["summary"])
    field("quality（覆盖投影，不表示业务测试通过）", report["quality"])
    table(
        ("目标", "覆盖", "缺口"),
        [
            (item["target_id"], item["status"], "；".join(item["missing_information"]))
            for item in payload["coverage"]
        ],
    )
    checks = {item["check_id"]: item for item in report["check_manifest"]}
    field(
        "逐目标覆盖的来源片段",
        [
            {"target_id": item["target_id"], "source_refs": item["source_refs"]}
            for item in payload["coverage"]
        ],
    )
    table(
        ("检查项", "冻结行为", "结果", "缺口"),
        [
            (
                item["check_id"],
                checks[item["check_id"]]["behavior"],
                item["status"],
                "；".join(item["missing_information"]),
            )
            for item in payload["check_results"]
        ],
    )
    field(
        "逐检查项：冻结行为与结果",
        [{"check": checks[item["check_id"]], "result": item} for item in payload["check_results"]],
    )
    section("规则采用与原文")
    for rule in report["rules"]:
        lines.extend(["### " + escaped(rule["adoption_id"]), ""])
        field("规则原文", rule["body"])
        field(
            "来源、版本、范围与采用原因",
            {key: value for key, value in rule.items() if key != "body"},
        )
    if not report["rules"]:
        lines.extend(["没有规则采用记录。", ""])
    section("发现与证据")
    for finding in payload["findings"]:
        lines.extend(
            ["### " + escaped(finding["id"]) + " · " + escaped(finding["judgment_status"]), ""]
        )
        field("判断", finding["claim"])
        field(
            "影响产物、引用与真实验证状态",
            {key: value for key, value in finding.items() if key != "claim"},
        )
    section("人工问题与裁决边界")
    field("冻结报告问题（后续已答状态经问题查询读取）", payload["questions"])
    field("本次输入采用的答案", frozen["resolutions"])
    field("本次修订指令", frozen.get("review_directives", []))
    section("处理任务")
    lines.extend(["建议范围不是修改许可；execution_authorized 保持报告中的真实值。", ""])
    for item in payload["work_items"]:
        lines.extend(["### " + escaped(item["id"]) + " · " + escaped(item["title"]), ""])
        field("处理意图", item["handling_intent"])
        field(
            "依赖、建议范围、就绪与阻塞",
            {key: value for key, value in item.items() if key not in ("title", "handling_intent")},
        )
    if not payload["work_items"]:
        lines.extend(["无处理任务。", ""])
    section("验收项")
    for item in payload["acceptance_items"]:
        lines.extend(["### " + escaped(item["id"]), ""])
        for name, label in (("given", "前提"), ("when", "核对动作"), ("then", "可检查结果")):
            field(label, item[name])
        field(
            "验收方法、环境、所需证据与执行状态",
            {key: value for key, value in item.items() if key not in ("given", "when", "then")},
        )
    if not payload["acceptance_items"]:
        lines.extend(["无验收项。", ""])
    section("外部核验与采用")
    lines.extend(
        [
            "外部记录及其采用不表示本系统执行或独立确认通过。"
            "null 适用性表示未确定，不能当作 false。",
            "",
        ]
    )
    field("原归属、提供者声明、报告输入采用与逐目标适用性", report["verification_evidence_summary"])
    section("委派验收与局限")
    field("父方验收", payload["adopted_child_result_refs"])
    field("局限与未覆盖范围", payload["limitations"])
    section("证据定位")
    base = f"/api/v1/contract-reviews/{review_id}"
    report_query = "report_revision_id=" + report["report_revision_id"]
    lines.extend(
        [
            f"- [本报告 JSON]({base}/report?{report_query})",
            f"- [本 job 事件与请求投影]({base}/events?job_id={job_id})",
            f"- [本报告问题与已答状态]({base}/questions?{report_query})",
            f"- [当前状态与 dispatch_gate]({base})",
            f"- [核验记录的当前采用视图]({base}/verification-evidence)",
            "",
            "按 event_id 读取同一认证边界的事件详情，可取得 payload 正文及请求材料投影；"
            "hash 仅用于完整性核对。",
            "",
        ]
    )
    return "\n".join(lines)
