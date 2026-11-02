"""Targetless intake, bounded queries and adoption inside formal input transactions."""

import base64
import json

from sqlalchemy import text

from specflow.contract_review.common import ReviewError, canonical, digest, identity, now
from specflow.contract_review.impact_schemas import DiscoveryProfile
from specflow.contract_review.schemas import Target
from specflow.contract_review.sources import select_text, strict_json


class ImpactService:
    def __init__(self, service, profiles=None):
        self.service, self.store = service, service.store
        self.profiles = {}
        for name, value in (profiles or {}).items():
            profile = DiscoveryProfile.model_validate(value)
            if name != profile.profile_id:
                raise RuntimeError("Discovery profile registration identity mismatch")
            self.profiles[name] = profile.frozen()

    def require(self, conn, discovery_id):
        row = self.store.row(
            conn, "SELECT * FROM contract_impact_discoveries WHERE id=:id", id=discovery_id
        )
        if row is None:
            raise ReviewError("RESOURCE_NOT_FOUND", "候选发现不存在。", 404)
        return row

    def charge(self, conn, discovery_id, count):
        self.store.reserve_records(conn, count)
        changed = self.store.execute(
            conn,
            "UPDATE contract_impact_discoveries SET record_bytes=record_bytes+:size "
            "WHERE id=:id AND record_bytes+:size<=:cap",
            id=discovery_id,
            size=count,
            cap=8 * 1024**2,
        )
        if changed.rowcount != 1:
            raise ReviewError("STORAGE_CAPACITY_EXCEEDED", "本次发现记录容量不足。", 503)

    def put(self, conn, row, body, *, status=None):
        raw = canonical(body)
        self.charge(conn, row["id"], max(0, len(raw.encode()) - len(row["body"].encode())))
        self.store.execute(
            conn,
            "UPDATE contract_impact_discoveries SET body=:body,status=:status,"
            "version=version+1 WHERE id=:id",
            id=row["id"],
            body=raw,
            status=status or row["status"],
        )

    def event(self, conn, discovery_id, event_type, payload):
        self.store.execute(
            conn,
            "UPDATE contract_impact_discoveries SET event_seq=event_seq+1 WHERE id=:id",
            id=discovery_id,
        )
        row = self.require(conn, discovery_id)
        metadata = dict(
            event_id=identity("ievt"),
            discovery_id=discovery_id,
            event_seq=row["event_seq"],
            event_type=event_type,
            payload_hash=digest(payload),
            occurred_at=now(),
        )
        body, content = canonical(metadata), canonical(payload)
        self.charge(conn, discovery_id, len(body.encode()) + len(content.encode()))
        self.store.execute(
            conn,
            "INSERT INTO contract_impact_events VALUES (:id,:discovery,:seq,:type,:body,:payload)",
            id=metadata["event_id"],
            discovery=discovery_id,
            seq=metadata["event_seq"],
            type=event_type,
            body=body,
            payload=content,
        )
        return metadata

    def snapshot(self, conn, body):
        frozen = body["frozen"]
        row = self.store.row(
            conn,
            "SELECT project_id FROM contract_review_snapshots WHERE id=:id",
            id=frozen["snapshot_id"],
        )
        if row is None or row["project_id"] != frozen["project_id"]:
            raise ReviewError("SOURCE_INTEGRITY_FAILED", "发现快照归属不完整。")
        return self.service.checkpoints._snapshot(conn, frozen)

    def rules(self, conn, request, profile):
        version = self.service.decisions.check_usage(
            conn, request.project_id, request.ruleset_usage.model_dump(), profile
        )
        return (
            []
            if version is None
            else [
                value
                for value in self.service.decisions.views(
                    self.service.decisions.records(conn, request.project_id, version)
                )
                if value["operation"] != "withdraw"
            ]
        )

    def create(self, request, key):
        payload = request.model_dump(exclude_none=True)
        scope = "service:impact:create:" + request.project_id
        key_hash, payload_hash = self.service.key_hash(key), digest(payload)
        with self.store.read() as conn:
            replay = self.service.replay(conn, scope, key_hash, payload_hash)
            if replay:
                return replay
            profile = self.profiles.get(request.execution_profile_id)
            if profile is None:
                raise ReviewError("RETRY_PROFILE_UNAVAILABLE", "发现 profile 未登记。")
            project = self.store.row(
                conn, "SELECT repository_path FROM projects WHERE id=:id", id=request.project_id
            )
            if project is None:
                raise ReviewError("PROJECT_NOT_FOUND", "项目不存在。", 404)
            repository = project["repository_path"]
            self.service.capacity(conn)
            rules = self.rules(conn, request, profile)
        snapshot = self.service.snapshot_reader.prepare(repository, request.source)
        sources = {source["path"]: source for source in snapshot["files"]}
        authorities = []
        for binding in payload["authority_bindings"]:
            source = sources.get(binding["path"])
            if source is None or not set(source["roles"]) & {"contract", "decision_reference"}:
                raise ReviewError("INVALID_AUTHORITY_BINDING", "规则不属于允许规范来源。", 422)
            content = select_text(source["body"], binding["selector"])
            authorities.append(
                dict(
                    source_ref=dict(source_id=source["source_id"], selector=binding["selector"]),
                    body=content,
                    body_hash=digest(content.encode()),
                    scope=binding["scope"],
                    purpose=binding["purpose"],
                )
            )
        discovery_id = identity("impact")
        frozen = dict(
            discovery_id=discovery_id,
            project_id=request.project_id,
            snapshot_id=snapshot["snapshot_id"],
            commit_sha=snapshot["commit_sha"],
            original_request=payload,
            change_request=request.change_request,
            authority_materials=authorities,
            confirmed_rules=rules,
            execution_profile=profile,
            profile_hash=digest(profile),
        )
        frozen["input_hash"] = digest(frozen)
        body = dict(
            frozen=frozen,
            repository=repository,
            budget=dict(
                model_calls=0,
                tool_actions=0,
                execution_seconds_charged=0.0,
                execution_seconds_reserved=0.0,
            ),
            catalog=None,
            error_code=None,
            started_at=None,
            deadline=None,
            finished_at=None,
        )
        raw, created = canonical(body), now()
        response = dict(
            discovery_id=discovery_id, status="queued", version=1, input_hash=frozen["input_hash"]
        )
        with self.store.transaction() as conn:
            replay = self.service.replay(conn, scope, key_hash, payload_hash)
            if replay:
                return replay
            self.service.capacity(conn, snapshot["byte_count"])
            current = self.store.row(
                conn, "SELECT repository_path FROM projects WHERE id=:id", id=request.project_id
            )
            if current is None or current["repository_path"] != repository:
                raise ReviewError("PROJECT_NOT_FOUND", "项目来源已变化。", 404)
            self.service.snapshot_reader.validate_path(repository)
            if self.rules(conn, request, profile) != rules:
                raise ReviewError("RULESET_VERSION_CONFLICT", "冻结规则已变化。")
            self.service.save_snapshot(conn, request.project_id, snapshot)
            self.store.reserve_records(conn, len(raw.encode()))
            self.store.execute(
                conn,
                "INSERT INTO contract_impact_discoveries "
                "(id,project_id,snapshot_id,status,version,body,created_at,record_bytes) "
                "VALUES (:id,:project,:snapshot,'queued',1,:body,:at,:size)",
                id=discovery_id,
                project=request.project_id,
                snapshot=snapshot["snapshot_id"],
                body=raw,
                at=created,
                size=len(raw.encode()),
            )
            self.event(conn, discovery_id, "discovery_created", response)
            return self.service.remember(conn, scope, key_hash, payload_hash, 202, response)

    def get(self, discovery_id):
        with self.store.read() as conn:
            row = self.require(conn, discovery_id)
            body = json.loads(row["body"])
            calls = [
                json.loads(value[0])
                for value in conn.execute(
                    text(
                        "SELECT body FROM contract_impact_calls WHERE discovery_id=:id ORDER BY id"
                    ),
                    dict(id=discovery_id),
                )
            ]
            return dict(
                discovery_id=discovery_id,
                project_id=row["project_id"],
                status=row["status"],
                version=row["version"],
                snapshot_id=row["snapshot_id"],
                input_hash=body["frozen"]["input_hash"],
                execution_profile=body["frozen"]["execution_profile"],
                budget=body["budget"],
                catalog=body["catalog"],
                error_code=body["error_code"],
                deadline=body["deadline"],
                started_at=body["started_at"],
                finished_at=body["finished_at"],
                unknown_usage_calls=sum(
                    call["kind"] == "model" and any(v is None for v in call["usage"].values())
                    for call in calls
                ),
                dispatch_gate=self.service.worker.dispatch_gate(conn)
                if self.service.worker
                else dict(can_claim=False, reason_codes=["runtime_not_ready"], blocked_by=[]),
            )

    def events(self, discovery_id, cursor=None, limit=20):
        after = 0
        if cursor:
            try:
                value = strict_json(base64.urlsafe_b64decode(cursor).decode())
                if (
                    set(value) != {"discovery", "after"}
                    or value["discovery"] != discovery_id
                    or type(value["after"]) is not int
                    or value["after"] < 1
                ):
                    raise ValueError("Invalid cursor")
                after = value["after"]
            except (ValueError, TypeError, UnicodeError) as error:
                raise ReviewError("INVALID_CURSOR", "发现游标归属无效。", 422) from error
        with self.store.read() as conn:
            self.require(conn, discovery_id)
            rows = conn.execute(
                text(
                    "SELECT body FROM contract_impact_events "
                    "WHERE discovery_id=:id AND event_seq>:seq ORDER BY event_seq LIMIT :limit"
                ),
                dict(id=discovery_id, seq=after, limit=limit + 1),
            ).all()
            items = [json.loads(row[0]) for row in rows[:limit]]
            next_cursor = (
                base64.urlsafe_b64encode(
                    canonical(dict(discovery=discovery_id, after=items[-1]["event_seq"])).encode()
                ).decode()
                if len(rows) > limit
                else None
            )
            return dict(items=items, next_cursor=next_cursor)

    def event_detail(self, discovery_id, event_id):
        with self.store.read() as conn:
            self.require(conn, discovery_id)
            row = self.store.row(
                conn,
                "SELECT body,payload FROM contract_impact_events "
                "WHERE id=:id AND discovery_id=:discovery",
                id=event_id,
                discovery=discovery_id,
            )
            if row is None:
                raise ReviewError("RESOURCE_NOT_FOUND", "事件不属于该发现。", 404)
            metadata, payload = json.loads(row["body"]), json.loads(row["payload"])
            if digest(payload) != metadata["payload_hash"]:
                raise ReviewError("SOURCE_INTEGRITY_FAILED", "事件正文已损坏。")
            return {**metadata, "payload": payload}

    def adoption_context(self, discovery_id, request, key):
        payload = request.model_dump(exclude_none=True)
        return dict(
            discovery_id=discovery_id,
            request=request,
            payload=payload,
            scope="impact:" + discovery_id + ":adopt",
            key_hash=self.service.key_hash(key),
            payload_hash=digest(payload),
            adoption_id=identity("iadopt"),
        )

    def adopt(self, discovery_id, request, key):
        context = self.adoption_context(discovery_id, request, key)
        with self.store.read() as conn:
            self.require(conn, discovery_id)
            replay = self.service.replay(
                conn, context["scope"], context["key_hash"], context["payload_hash"]
            )
            if replay:
                return replay
        destination = request.destination
        if destination is None:
            with self.store.transaction() as conn:
                replay = self.service.replay(
                    conn, context["scope"], context["key_hash"], context["payload_hash"]
                )
                if replay:
                    return replay
                self.prepare_adoption(conn, context, None, None)
                response = dict(
                    adoption_id=context["adoption_id"],
                    discovery_id=discovery_id,
                    status="recorded",
                    accepted=True,
                )
                self.commit_adoption(conn, context, None, response, status=201)
                return 201, response
        inner_key = "impact:" + digest(dict(key=key, payload=context["payload"], id=discovery_id))
        if destination.kind == "create":
            return self.service.create(destination.request, inner_key, impact_adoption=context)
        return self.service.checkpoints.revise(
            destination.review_id, destination.request, inner_key, impact_adoption=context
        )

    def prepare_adoption(self, conn, context, frozen, snapshot):
        request = context["request"]
        prior = self.service.replay(
            conn, context["scope"], context["key_hash"], context["payload_hash"]
        )
        if prior:
            raise ReviewError("IDEMPOTENCY_KEY_REUSED", "采用已提交，需读取原响应。")
        row = self.require(conn, context["discovery_id"])
        body = json.loads(row["body"])
        catalog = body["catalog"]
        if row["status"] != "completed" or catalog is None:
            raise ReviewError("INVALID_STATE", "只能采用已完成且宿主接受的候选目录。")
        if digest(
            {key: value for key, value in catalog.items() if key != "catalog_hash"}
        ) != catalog["catalog_hash"] or (request.catalog_hash != catalog["catalog_hash"]):
            raise ReviewError("VERSION_CONFLICT", "候选目录已变化。")
        candidates = {value["candidate_id"]: value for value in catalog["candidates"]}
        if {value.candidate_id for value in request.dispositions} != set(candidates):
            raise ReviewError("INPUT_SCOPE_CONFLICT", "必须逐项处置本目录的全部候选。")
        if frozen is None:
            return
        original = body["frozen"]
        raw = frozen["original_request"]
        project = self.store.row(
            conn, "SELECT repository_path FROM projects WHERE id=:id", id=original["project_id"]
        )
        if (
            raw["project_id"] != original["project_id"]
            or project is None
            or project["repository_path"] != body["repository"]
            or frozen["commit_sha"] != original["commit_sha"]
        ):
            raise ReviewError("INPUT_SCOPE_CONFLICT", "采用项目或固定来源不一致。")
        self.service.snapshot_reader.validate_path(body["repository"])
        allowed = {value["path"]: value for value in self.snapshot(conn, body)["files"]}
        for value in snapshot["files"]:
            old = allowed.get(value["path"])
            if (
                old is None
                or value["body_hash"] != old["body_hash"]
                or not set(value["roles"]) <= set(old["roles"])
            ):
                raise ReviewError("INPUT_SCOPE_CONFLICT", "正式来源扩大了已取证范围。")
        if raw["ruleset_usage"] != original["original_request"]["ruleset_usage"]:
            raise ReviewError("INPUT_SCOPE_CONFLICT", "规则选择变化需要单独明确取证。")
        targets = raw["targets"]
        selected, mapping = [], []
        for choice in request.dispositions:
            if choice.disposition == "exclude":
                continue
            index = choice.target_index
            if index >= len(targets):
                raise ReviewError("INPUT_SCOPE_CONFLICT", "采用目标索引不存在。")
            candidate = candidates[choice.candidate_id]
            if choice.disposition == "take":
                expected = dict(
                    source_path=candidate["source_path"], checks=candidate["suggested_checks"]
                )
                expected.update(
                    {
                        name: candidate[name]
                        for name in ("api_version", "endpoint")
                        if name in candidate
                    }
                )
                try:
                    same = Target.model_validate(expected).model_dump(exclude_none=True) == (
                        Target.model_validate(targets[index]).model_dump(exclude_none=True)
                    )
                except ValueError:
                    same = False
                if not same:
                    raise ReviewError("INPUT_SCOPE_CONFLICT", "候选更正必须声明 edit 及理由。")
            selected.append(index)
            target_id = frozen["target_manifest"][index]["target_id"]
            mapping.append(
                dict(
                    candidate_id=choice.candidate_id,
                    target_id=target_id,
                    check_ids=[
                        check["check_id"]
                        for check in frozen["check_manifest"]
                        if check["target_id"] == target_id
                    ],
                )
            )
        selected.extend(item.target_index for item in request.manual_additions)
        if sorted(selected) != list(range(len(targets))):
            raise ReviewError("INPUT_SCOPE_CONFLICT", "正式目标需由采用或人工新增唯一解释。")
        context["mapping"] = mapping
        frozen["impact_origin"] = dict(
            adoption_id=context["adoption_id"],
            discovery_id=context["discovery_id"],
            catalog_hash=request.catalog_hash,
            candidate_mapping=mapping,
            manual_additions=context["payload"]["manual_additions"],
        )

    def commit_adoption(self, conn, context, frozen, response, *, status=202):
        response.update(adoption_id=context["adoption_id"], discovery_id=context["discovery_id"])
        record = dict(
            adoption_id=context["adoption_id"],
            discovery_id=context["discovery_id"],
            request=context["payload"],
            candidate_mapping=context.get("mapping", []),
            review_id=response.get("review_id"),
            input_revision_id=response.get("input_revision_id"),
            created_at=now(),
        )
        raw = canonical(record)
        self.charge(conn, context["discovery_id"], len(raw.encode()))
        self.store.execute(
            conn,
            "INSERT INTO contract_impact_adoptions VALUES "
            "(:id,:discovery,:review,:input,:body,:at)",
            id=context["adoption_id"],
            discovery=context["discovery_id"],
            review=record["review_id"],
            input=record["input_revision_id"],
            body=raw,
            at=record["created_at"],
        )
        self.event(conn, context["discovery_id"], "adoption_recorded", record)
        self.service.remember(
            conn, context["scope"], context["key_hash"], context["payload_hash"], status, response
        )
