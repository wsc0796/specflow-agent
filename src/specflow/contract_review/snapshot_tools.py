"""Read-only tools over sealed UTF-8 source bodies and explicit fragment grants."""

import base64
import posixpath
from copy import deepcopy
from urllib.parse import unquote, urlsplit

from pydantic import ValidationError

from specflow.contract_review.common import ReviewError, canonical, digest
from specflow.contract_review.python_inspection import inspect_python
from specflow.contract_review.schemas import JsonSelector
from specflow.contract_review.sources import select_text, strict_json
from specflow.contract_review.tool_protocol import TOOL_ARGUMENTS, covers_selector


class SnapshotTools:
    def __init__(self, sources, snapshot_id, grants=None, allowed_tools=None):
        self.sources = sources
        self.snapshot_id = snapshot_id
        self.grants = grants if grants is not None else {key: [{"kind": "full"}] for key in sources}
        self.allowed_tools = set(TOOL_ARGUMENTS if allowed_tools is None else allowed_tools)

    def permitted(self, source_id, selector):
        source = self.sources.get(source_id)
        return source is not None and covers_selector(
            self.grants.get(source_id, []), selector, len(source["body"].splitlines())
        )

    def _source(self, source_id):
        source = self.sources[source_id]
        if digest(source["body"].encode("utf-8")) != source["body_hash"]:
            raise ReviewError("SOURCE_INTEGRITY_FAILED", "密封来源正文校验失败。")
        return source

    def _catalog(self, arguments):
        return sorted(
            (
                source
                for key, source in self.sources.items()
                if key in self.grants
                and source["path"].startswith(arguments["path_prefix"])
                and (not arguments.get("roles") or set(source["roles"]) & set(arguments["roles"]))
            ),
            key=lambda item: (item["path"], item["source_id"]),
        )

    def _cursor_scope(self, arguments):
        return digest(
            {
                "snapshot": self.snapshot_id,
                "grants": self.grants,
                "roles": arguments.get("roles"),
                "path_prefix": arguments["path_prefix"],
            }
        )

    def _after(self, arguments, catalog):
        if not arguments.get("cursor"):
            return 0
        try:
            cursor = strict_json(base64.urlsafe_b64decode(arguments["cursor"]).decode("utf-8"))
            if set(cursor) != {"scope", "last"} or cursor["scope"] != self._cursor_scope(arguments):
                raise ValueError("Cursor scope mismatch")
            return next(
                index + 1
                for index, item in enumerate(catalog)
                if item["source_id"] == cursor["last"]
            )
        except (ValueError, TypeError, KeyError, StopIteration, UnicodeError) as error:
            raise ReviewError("ACTION_SCHEMA_INVALID", "来源游标无效或越过允许范围。") from error

    def validate(self, name, arguments):
        if name not in TOOL_ARGUMENTS:
            raise ReviewError("ACTION_SCHEMA_INVALID", "工具未登记。")
        if name not in self.allowed_tools:
            raise ReviewError("ACTION_PERMISSION_DENIED", "该职责无权调用此工具。")
        try:
            args = TOOL_ARGUMENTS[name].model_validate(arguments).model_dump(exclude_none=True)
        except ValidationError as error:
            raise ReviewError("ACTION_SCHEMA_INVALID", "工具参数不符合登记协议。") from error
        if name == "list_sources":
            self._after(args, self._catalog(args))
            return args
        if name == "search_sources":
            if any(
                identifier not in self.grants or identifier not in self.sources
                for identifier in args["source_ids"]
            ):
                raise ReviewError("ACTION_PERMISSION_DENIED", "搜索来源超出允许集合。")
            return args
        source_id = args["source_id"]
        selector = (
            {"kind": "lines", "start_line": args["start_line"], "end_line": args["end_line"]}
            if name == "read_source"
            else {"kind": "json_pointer", "pointer": args["pointer"]}
            if name == "inspect_json_contract"
            else {"kind": "full"}
        )
        if not self.permitted(source_id, selector):
            raise ReviewError("ACTION_PERMISSION_DENIED", "读取片段超出当前职责允许范围。")
        if name == "read_source" and args["end_line"] > len(
            self.sources[source_id]["body"].splitlines()
        ):
            raise ReviewError("ACTION_SCHEMA_INVALID", "读取行号超出来源范围。")
        if name == "inspect_json_contract" and any(
            identifier not in self.grants or identifier not in self.sources
            for identifier in args["local_ref_source_ids"]
        ):
            raise ReviewError("ACTION_PERMISSION_DENIED", "本地 JSON 引用来源越界。")
        return args

    @staticmethod
    def _result(body, refs=(), kind="data", *, truncated=False, truncation=None, error=None):
        value = {
            "result_kind": kind,
            "body": body,
            "source_refs": list(refs),
            "completeness": "truncated" if truncated else "complete",
            "truncation": truncation,
            "error": error,
        }
        encoded = canonical(value).encode("utf-8")
        if len(encoded) > 64 * 1024:
            raw = canonical(body).encode("utf-8")
            value.update(
                body={"text_prefix": raw[:48000].decode("utf-8", errors="ignore")},
                source_refs=[],
                completeness="truncated",
                truncation={"original_bytes": len(raw), "retained_max_bytes": 48000},
            )
        return value

    def execute(self, name, arguments):
        # Callers validate before creating an I/O intent; recheck at the handler
        # boundary too so another in-process caller cannot widen its grants.
        args = self.validate(name, arguments)
        try:
            return getattr(self, "_" + name)(args)
        except (SyntaxError, ValueError, RecursionError, KeyError) as error:
            return self._result(
                {},
                kind="dependency_error",
                error={"code": "SOURCE_PARSE_FAILED", "type": type(error).__name__},
            )
        except ReviewError as error:
            return self._result({}, kind="dependency_error", error={"code": error.code})

    def _list_sources(self, args):
        catalog, items = self._catalog(args), []
        after = self._after(args, catalog)
        for source in catalog[after : after + args["limit"]]:
            item = {key: source[key] for key in ("source_id", "path", "roles", "body_hash")}
            item["allowed_selectors"] = self.grants[source["source_id"]]
            item["line_count"] = len(source["body"].splitlines())
            if items and len(canonical(items + [item]).encode("utf-8")) > 48000:
                break
            items.append(item)
        cursor = None
        if after + len(items) < len(catalog):
            cursor = base64.urlsafe_b64encode(
                canonical(
                    {"scope": self._cursor_scope(args), "last": items[-1]["source_id"]}
                ).encode()
            ).decode()
        return self._result(
            {"items": items, "next_cursor": cursor}, kind="data" if items else "empty"
        )

    def _read_source(self, args):
        source = self._source(args["source_id"])
        lines = source["body"].splitlines(keepends=True)
        requested = "".join(lines[args["start_line"] - 1 : args["end_line"]])
        text, complete_end = "", args["start_line"] - 1
        for number in range(args["start_line"], args["end_line"] + 1):
            line = lines[number - 1]
            remaining = 8000 - len(text)
            text += line[:remaining]
            if len(line) > remaining:
                break
            complete_end = number
        refs = []
        if complete_end >= args["start_line"]:
            refs = [
                {
                    "source_id": args["source_id"],
                    "selector": {
                        "kind": "lines",
                        "start_line": args["start_line"],
                        "end_line": complete_end,
                    },
                }
            ]
        truncated = len(text) < len(requested)
        return self._result(
            {
                "text": text,
                "requested_range": [args["start_line"], args["end_line"]],
                "complete_line_range": [args["start_line"], complete_end] if refs else None,
                "next_range": [complete_end + 1, args["end_line"]] if truncated else None,
            },
            refs,
            truncated=truncated,
            truncation={"original_characters": len(requested), "retained_characters": len(text)}
            if truncated
            else None,
        )

    def _search_sources(self, args):
        matches, refs, seen = [], [], set()
        needle = args["query"] if args["case_sensitive"] else args["query"].casefold()
        truncated = False
        for source_id in args["source_ids"]:
            source = self._source(source_id)
            lines = source["body"].splitlines(keepends=True)
            for grant in self.grants[source_id]:
                if grant["kind"] == "json_pointer":
                    candidates = [(grant, select_text(source["body"], grant))]
                else:
                    start = grant.get("start_line", 1)
                    end = min(grant.get("end_line", len(lines)), len(lines))
                    candidates = [
                        (
                            {"kind": "lines", "start_line": index, "end_line": index},
                            lines[index - 1],
                        )
                        for index in range(start, end + 1)
                    ]
                for selector, body in candidates:
                    if needle not in (body if args["case_sensitive"] else body.casefold()):
                        continue
                    ref = {"source_id": source_id, "selector": selector}
                    if canonical(ref) in seen:
                        continue
                    seen.add(canonical(ref))
                    if len(matches) >= args["max_matches"]:
                        truncated = True
                        break
                    matches.append(
                        {"source_ref": ref, "text": body[:8000], "truncated": len(body) > 8000}
                    )
                    if len(body) <= 8000:
                        refs.append(ref)
                    else:
                        truncated = True
                if len(matches) >= args["max_matches"] and truncated:
                    break
            if len(matches) >= args["max_matches"] and truncated:
                break
        return self._result(
            {"query": args["query"], "source_ids": args["source_ids"], "matches": matches},
            refs,
            "data" if matches else "empty",
            truncated=truncated,
            truncation={"max_matches": args["max_matches"], "text_limit": 8000}
            if truncated
            else None,
        )

    def _inspect_python_contract(self, args):
        source = self._source(args["source_id"])
        if not source["path"].lower().endswith(".py"):
            return self._result({}, kind="unsupported", error={"code": "UNSUPPORTED_SOURCE_TYPE"})
        result = inspect_python(source["body"], args["selectors"])
        refs = []
        for fact in result["facts"]:
            if not fact["truncated"]:
                ref = {
                    "source_id": args["source_id"],
                    "selector": {
                        "kind": "lines",
                        "start_line": fact["start_line"],
                        "end_line": fact["end_line"],
                    },
                }
                if ref not in refs:
                    refs.append(ref)
        return self._result(
            result,
            refs,
            "unsupported" if result["unsupported"] else "data" if result["facts"] else "empty",
        )

    def _inspect_json_contract(self, args):
        source_id = args["source_id"]
        source = self._source(source_id)
        if not source["path"].lower().endswith(".json"):
            return self._result({}, kind="unsupported", error={"code": "UNSUPPORTED_SOURCE_TYPE"})
        selector = {"kind": "json_pointer", "pointer": args["pointer"]}
        selected = strict_json(select_text(source["body"], selector))
        refs = [{"source_id": source_id, "selector": selector}]
        resolutions, unsupported, visited, active = [], [], set(), set()
        paths = {value["path"]: key for key, value in self.sources.items()}
        nodes = 0

        def walk(value, current_id, depth=0):
            nonlocal nodes
            nodes += 1
            if depth > 12 or nodes > 2000:
                if "resolution_limit" not in unsupported:
                    unsupported.append("resolution_limit")
                return
            if isinstance(value, dict):
                reference = value.get("$ref")
                if reference is not None:
                    if not isinstance(reference, str) or len(reference) > 1024:
                        unsupported.append("invalid_reference")
                    else:
                        location = urlsplit(reference)
                        if (
                            location.scheme
                            or location.netloc
                            or location.query
                            or "\\" in location.path
                        ):
                            unsupported.append("external_reference")
                        else:
                            path = posixpath.normpath(
                                posixpath.join(
                                    posixpath.dirname(self.sources[current_id]["path"]),
                                    unquote(location.path),
                                )
                            )
                            target = current_id if not location.path else paths.get(path)
                            pointer = unquote(location.fragment)
                            try:
                                JsonSelector(kind="json_pointer", pointer=pointer)
                            except ValueError:
                                unsupported.append("invalid_reference_pointer")
                                return
                            allowed = target == current_id or target in args["local_ref_source_ids"]
                            requested = {"kind": "json_pointer", "pointer": pointer}
                            if not target or not allowed or not self.permitted(target, requested):
                                unsupported.append("reference_not_allowed")
                            elif (target, pointer) in active:
                                unsupported.append("reference_cycle")
                            elif (target, pointer) not in visited:
                                visited.add((target, pointer))
                                active.add((target, pointer))
                                nested = strict_json(
                                    select_text(self._source(target)["body"], requested)
                                )
                                resolutions.append(
                                    {"source_id": target, "pointer": pointer, "value": nested}
                                )
                                ref = {"source_id": target, "selector": requested}
                                if ref not in refs:
                                    refs.append(ref)
                                walk(nested, target, depth + 1)
                                active.remove((target, pointer))
                for key, item in value.items():
                    if key != "$ref":
                        walk(item, current_id, depth + 1)
            elif isinstance(value, list):
                for item in value:
                    walk(item, current_id, depth + 1)

        walk(selected, source_id)
        return self._result(
            {
                "value": deepcopy(selected),
                "resolved_refs": resolutions,
                "unsupported": sorted(set(unsupported)),
            },
            refs,
            "unsupported" if unsupported else "data",
        )
