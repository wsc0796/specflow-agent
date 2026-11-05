"""Finite syntactic facts for direct FastAPI-style declarations; never imports source."""

import ast
from collections import Counter


class ModuleBindings(ast.NodeVisitor):
    """Conservatively count module bindings without entering local scopes."""

    def __init__(self):
        self.counts = Counter()

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Store | ast.Del):
            self.counts[node.id] += 1

    def visit_Import(self, node):
        for item in node.names:
            self.counts[item.asname or item.name.split(".")[0]] += 1

    def visit_ImportFrom(self, node):
        for item in node.names:
            self.counts[item.asname or item.name] += 1

    def visit_FunctionDef(self, node):
        self.counts[node.name] += 1

    visit_AsyncFunctionDef = visit_ClassDef = visit_FunctionDef

    def visit_Lambda(self, node):
        pass


def inspect_python(body, selectors):
    tree = ast.parse(body)
    lines, facts, unsupported = body.splitlines(keepends=True), [], []
    imported, instances, edges, models = {}, {}, [], {}
    collector = ModuleBindings()
    collector.visit(tree)
    bindings = collector.counts
    for node in tree.body:
        if (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module in ("fastapi", "pydantic")
        ):
            for item in node.names:
                imported[item.asname or item.name] = node.module + "." + item.name
        if isinstance(node, ast.Import):
            for item in node.names:
                if item.name in ("fastapi", "pydantic"):
                    imported[item.asname or item.name] = item.name
    imported = {key: value for key, value in imported.items() if bindings[key] == 1}

    def local_nodes(node):
        yield node
        for child in ast.iter_child_nodes(node):
            if not isinstance(
                child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Lambda
            ):
                yield from local_nodes(child)

    def name(node, *, imported_only=False):
        if isinstance(node, ast.Name):
            return imported.get(node.id, "<dynamic>" if imported_only else node.id)
        if isinstance(node, ast.Attribute):
            return name(node.value, imported_only=imported_only) + "." + node.attr
        return "<dynamic>"

    def literal(node, default=None):
        try:
            return ast.literal_eval(node)
        except (ValueError, TypeError):
            return default

    def emit(kind, node, **data):
        start, end = node.lineno, node.end_lineno
        snippet = "".join(lines[start - 1 : end])
        facts.append(
            {
                "kind": kind,
                **data,
                "start_line": start,
                "end_line": end,
                "text": snippet[:8000],
                "truncated": len(snippet) > 8000,
            }
        )

    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            key = node.targets[0].id
            if isinstance(node.value, ast.Call) and name(node.value.func, imported_only=True) in (
                "fastapi.FastAPI",
                "fastapi.APIRouter",
            ):
                kwargs = {kw.arg: kw.value for kw in node.value.keywords}
                prefix = literal(kwargs["prefix"]) if "prefix" in kwargs else ""
                instances[key] = {
                    "root": name(node.value.func, imported_only=True) == "fastapi.FastAPI",
                    "prefix": prefix if bindings[key] == 1 else None,
                    "node": node,
                }
            elif key in instances:
                instances[key]["prefix"] = None
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if isinstance(call.func, ast.Attribute) and call.func.attr == "include_router":
                parent = call.func.value.id if isinstance(call.func.value, ast.Name) else None
                child = (
                    call.args[0].id if call.args and isinstance(call.args[0], ast.Name) else None
                )
                kwargs = {kw.arg: kw.value for kw in call.keywords}
                prefix = literal(kwargs["prefix"]) if "prefix" in kwargs else ""
                edges.append((parent, child, prefix, node))
        if isinstance(node, ast.ClassDef):
            valid = (
                len(node.bases) == 1
                and name(node.bases[0], imported_only=True) == "pydantic.BaseModel"
                and not node.decorator_list
                and not node.keywords
            )
            fields = []
            for field in node.body:
                if isinstance(field, ast.AnnAssign) and isinstance(field.target, ast.Name):
                    valid &= isinstance(field.annotation, ast.Name) and field.annotation.id in (
                        "str",
                        "int",
                        "float",
                        "bool",
                    )
                    valid &= field.value is None or isinstance(field.value, ast.Constant)
                    fields.append(field.target.id)
                elif not (
                    isinstance(field, ast.Pass)
                    or isinstance(field, ast.Expr)
                    and isinstance(field.value, ast.Constant)
                ):
                    valid = False
            models[node.name] = (
                valid
                and bool(fields)
                and len(set(fields)) == len(fields)
                and bindings[node.name] == 1,
                fields,
                node,
            )

    def prefixes(receiver, seen=()):
        if receiver in seen or receiver not in instances:
            return [], []
        instance = instances[receiver]
        if not isinstance(instance["prefix"], str):
            return [], []
        if instance["root"]:
            return [""], [instance["node"]]
        paths, evidence = [], [instance["node"]]
        for parent, child, prefix, node in edges:
            if child != receiver:
                continue
            if not isinstance(prefix, str):
                return [], []
            outer, proof = prefixes(parent, (*seen, receiver))
            if not outer:
                return [], []
            paths.extend(item + prefix + instance["prefix"] for item in outer)
            evidence.extend([*proof, node])
        return paths, evidence

    methods = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
    for function in [
        node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    ]:
        route_decorators = [
            node
            for node in function.decorator_list
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in methods
        ]
        if function not in tree.body and route_decorators:
            unsupported.append({"function": function.name, "reason": "nested_dynamic_registration"})
            route_decorators = []
        for decorator in function.decorator_list:
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id in instances
                and decorator.func.attr not in methods
            ):
                unsupported.append(
                    {"function": function.name, "reason": "unsupported_route_decorator"}
                )
        for route in route_decorators:
            receiver = route.func.value.id if isinstance(route.func.value, ast.Name) else None
            kwargs = {kw.arg: kw.value for kw in route.keywords}
            path = literal(route.args[0]) if route.args else literal(kwargs.get("path"))
            chain, proof = prefixes(receiver)
            if not isinstance(path, str) or not chain:
                unsupported.append(
                    {"function": function.name, "reason": "dynamic_or_incomplete_registration"}
                )
            elif "routes" in selectors:
                for prefix in chain:
                    emit("route", route, method=route.func.attr.upper(), path=prefix + path)
                for item in proof:
                    emit("registration", item)
            kwargs = {kw.arg: kw.value for kw in route.keywords}
            filtered = any(
                key is None or key.startswith("response_model_") or key == "response_class"
                for key in kwargs
            )
            extra_decorators = len(route_decorators) != len(function.decorator_list)
            if extra_decorators:
                unsupported.append({"function": function.name, "reason": "additional_decorators"})
            if "response_fields" in selectors:
                model = kwargs.get("response_model")
                if filtered or extra_decorators:
                    unsupported.append(
                        {"function": function.name, "reason": "response_filter_or_wrapper"}
                    )
                elif model is not None and not (
                    isinstance(model, ast.Constant) and model.value is None
                ):
                    key = model.id if isinstance(model, ast.Name) else ""
                    supported, fields, definition = models.get(key, (False, [], None))
                    if supported:
                        emit(
                            "response_model_fields",
                            definition,
                            function=function.name,
                            fields=fields,
                        )
                        emit("response_model_binding", route, model=key)
                    else:
                        unsupported.append(
                            {"function": function.name, "reason": "unsupported_response_model"}
                        )
                else:
                    if function.returns is not None and "response_model" not in kwargs:
                        unsupported.append(
                            {
                                "function": function.name,
                                "reason": "implicit_response_model_annotation",
                            }
                        )
                    else:
                        for returned in [
                            node for node in local_nodes(function) if isinstance(node, ast.Return)
                        ]:
                            value = returned.value
                            if isinstance(value, ast.Dict) and all(
                                isinstance(key, ast.Constant) and isinstance(key.value, str)
                                for key in value.keys
                            ):
                                emit(
                                    "returned_fields",
                                    returned,
                                    function=function.name,
                                    fields=[key.value for key in value.keys],
                                )
                            else:
                                unsupported.append(
                                    {"function": function.name, "reason": "dynamic_return"}
                                )
        if "state_guards" in selectors:
            for node in local_nodes(function):
                if isinstance(node, ast.If | ast.Raise):
                    emit(
                        "branch" if isinstance(node, ast.If) else "raise",
                        node,
                        function=function.name,
                    )
                if isinstance(node, ast.Call) and name(node.func) not in (
                    "fastapi.HTTPException",
                    "str",
                    "int",
                    "float",
                    "bool",
                    "len",
                    "dict",
                ):
                    unsupported.append(
                        {"function": function.name, "reason": "unresolved_called_behavior"}
                    )
            if route_decorators:
                emit(
                    "function_body",
                    function,
                    function=function.name,
                    interpretation="syntactic_only",
                )
    for node in ast.walk(tree):
        if "assignments" in selectors and isinstance(
            node, ast.Assign | ast.AnnAssign | ast.AugAssign
        ):
            emit("assignment", node)
        if "call_refs" in selectors and isinstance(node, ast.Call):
            emit("call_reference", node, callable=name(node.func), resolved=False)
    return {
        "facts": facts,
        "unsupported": unsupported,
        "support_matrix_version": "contract-static-support.v1",
    }
