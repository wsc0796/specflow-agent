"""One-request HTTP CLI; never imports the database, worker or model runner."""

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx

BODY_LIMIT = 1024**2
RESPONSE_LIMIT = 8 * 1024**2


def identifier(value):
    if (
        not 1 <= len(value) <= 64
        or value in (".", "..")
        or any(char in value for char in "/\\?#")
        or any(ord(char) < 33 for char in value)
    ):
        raise argparse.ArgumentTypeError("资源 ID 无效。")
    return value


def key(value):
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", value):
        raise argparse.ArgumentTypeError("幂等键须为 1—128 个字母、数字或 ._:-。")
    return value


def limit(value):
    number = int(value)
    if not 1 <= number <= 100:
        raise argparse.ArgumentTypeError("每页数量须为 1—100。")
    return number


def configure_parser(subparsers):
    parser = subparsers.add_parser("contract-review", help="通过认证 HTTP 查询及提交契约审查")
    parser.add_argument(
        "--base-url", default="http://127.0.0.1:8000", help="服务地址，不含凭据、查询或片段"
    )
    parser.add_argument(
        "--api-key-env", default="SPECFLOW_API_KEY", help="运行时读取服务认证的环境变量名"
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="单次 HTTP 超时秒数（0—60）")
    parser.add_argument(
        "--output", type=Path, help="导出到新文件；已有文件不覆盖，省略则输出到 stdout"
    )
    actions = parser.add_subparsers(dest="review_command", required=True)

    def action(name, *, review=False, project=False, post=False, paged=False):
        command = actions.add_parser(name)
        if review:
            command.add_argument("review_id", type=identifier)
        if project:
            command.add_argument("--project-id", required=True, type=identifier)
        if post:
            command.add_argument("--body-file", required=True, help="UTF-8 JSON 文件；- 表示 stdin")
            command.add_argument("--idempotency-key", required=True, type=key)
        if paged:
            command.add_argument("--cursor")
            command.add_argument("--limit", type=limit, default=20)
        return command

    action("create", post=True)
    action("list", project=True, paged=True)
    action("status", review=True)
    report = action("report", review=True)
    report.add_argument("--report-revision-id", type=identifier)
    report.add_argument("--format", choices=("json", "markdown"), default="markdown")
    action("questions", review=True).add_argument("--report-revision-id", type=identifier)
    action("events", review=True, paged=True).add_argument("--job-id", type=identifier)
    action("event", review=True).add_argument("event_id", type=identifier)
    action("resolve", review=True, post=True)
    action("revise", review=True, post=True)
    action("import-evidence", review=True, post=True)
    evidence = action("evidence", review=True, paged=True)
    evidence.add_argument("--evidence-id", type=identifier)
    evidence.add_argument("--input-revision-id", type=identifier)
    evidence.add_argument("--report-revision-id", type=identifier)
    action("decisions", project=True, paged=True).add_argument("--ruleset-version", type=int)
    action("publish-decision", project=True, post=True)


def body_from_file(filename):
    if filename == "-":
        raw = sys.stdin.buffer.read(BODY_LIMIT + 1)
    else:
        with Path(filename).open("rb") as handle:
            raw = handle.read(BODY_LIMIT + 1)
    if len(raw) > BODY_LIMIT:
        raise ValueError("请求正文超过 1 MiB。")

    def pairs(values):
        result = {}
        for name, value in values:
            if name in result:
                raise ValueError("JSON 字段重复。")
            result[name] = value
        return result

    def constant(_):
        raise ValueError("JSON 不允许非有限数字。")

    body = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    if not isinstance(body, dict):
        raise ValueError("请求正文须为 JSON 对象。")
    return body


def request_spec(args):
    command = args.review_command
    base = "/api/v1/contract-reviews"
    if hasattr(args, "review_id"):
        base += "/" + quote(args.review_id, safe="")
    paths = {
        "create": "",
        "list": "",
        "status": "",
        "report": "/report",
        "questions": "/questions",
        "events": "/events",
        "event": "/events/" + quote(getattr(args, "event_id", ""), safe=""),
        "resolve": "/resolution-batches",
        "revise": "/revisions",
        "import-evidence": "/verification-evidence",
        "evidence": "/verification-evidence",
    }
    if command in ("decisions", "publish-decision"):
        path = "/api/v1/projects/" + quote(args.project_id, safe="") + "/contract-decisions"
    else:
        path = base + paths[command]
    query = {}
    for name in (
        "cursor",
        "limit",
        "report_revision_id",
        "input_revision_id",
        "job_id",
        "ruleset_version",
    ):
        value = getattr(args, name, None)
        if value is not None:
            query[name] = value
    if command == "list":
        query["project_id"] = args.project_id
    if command == "report":
        query["format"] = args.format
    if command == "evidence" and args.evidence_id:
        if args.cursor or args.input_revision_id or args.report_revision_id or args.limit != 20:
            raise ValueError("核验详情不能同时提供列表过滤或分页参数。")
        path += "/" + quote(args.evidence_id, safe="")
        query = {}
    method = "POST" if hasattr(args, "body_file") else "GET"
    return method, path, query, body_from_file(args.body_file) if method == "POST" else None


def execute(args):
    status = None
    try:
        parsed = urlsplit(args.base_url)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in ("", "/")
            or any(ord(char) < 33 for char in args.base_url)
        ):
            raise ValueError("服务地址须为不含凭据、路径、查询或片段的 HTTP(S) 地址。")
        if not math.isfinite(args.timeout) or not 0 < args.timeout <= 60:
            raise ValueError("HTTP 超时须大于 0 且不超过 60 秒。")
        # Accessing port validates its syntax and range before credentials are read.
        parsed.port
        method, path, query, body = request_spec(args)
        # Read only on explicit invocation; tests supply a separate fake environment variable.
        credential = os.environ.get(args.api_key_env)
        if (
            not credential
            or not credential.isascii()
            or any(ord(char) < 33 or ord(char) == 127 for char in credential)
        ):
            raise ValueError("指定环境变量中没有可用的服务认证。")
        headers = {"X-API-Key": credential}
        if method == "POST":
            headers["Idempotency-Key"] = args.idempotency_key
        with httpx.Client(
            base_url=args.base_url.rstrip("/"),
            timeout=args.timeout,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            with client.stream(method, path, params=query, json=body, headers=headers) as response:
                status = response.status_code
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > RESPONSE_LIMIT:
                        raise ValueError("HTTP 响应超过 8 MiB；请缩小查询范围。")
                    chunks.append(chunk)
                raw = b"".join(chunks).decode("utf-8")
                status = response.status_code
        success = 200 <= status < 300
        if not success:
            print(f"HTTP {status}", file=sys.stderr)
            print(raw, file=sys.stderr)
            return 3
        output = (
            raw
            if args.review_command == "report" and args.format == "markdown"
            else json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
        )
    except (OSError, ValueError, UnicodeError, RecursionError, httpx.InvalidURL):
        print(
            "HTTP 响应未能读取或解析；服务端结果保留，写请求可用原幂等键重放。"
            if status is not None
            else "请求参数或 JSON 文件无效，或指定环境变量中没有可用的服务认证。",
            file=sys.stderr,
        )
        return 2
    except httpx.HTTPError:
        print("HTTP 请求未完成；写请求可用原幂等键重放，不自动重试。", file=sys.stderr)
        return 3
    try:
        if args.output:
            with args.output.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(output + "\n")
        else:
            print(output)
    except (OSError, UnicodeError):
        print(
            "HTTP 响应已收到，但输出失败；服务端结果保持原状，可查询或使用原幂等键重放。",
            file=sys.stderr,
        )
        return 2
    return 0
