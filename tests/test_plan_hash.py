from specflow.plan.hash_utils import (
    StructuralHashInput,
    compute_effective_plan_hash,
    compute_semantic_brief_hash,
    compute_structure_hash,
)


class TestStructureHash:
    def test_same_input_same_hash(self):
        inp = StructuralHashInput(
            agents=[{"agent_id": "a1", "role": "design", "version": "1.0.0"}],
            dependencies=[{"agent_id": "a1", "depends_on": []}],
            stages=[["a1"]],
            revision_policy={"max_total_rounds": 1},
        )
        assert compute_structure_hash(inp) == compute_structure_hash(inp)

    def test_different_agents_different_hash(self):
        a = StructuralHashInput(
            agents=[{"agent_id": "a1", "role": "design", "version": "1.0.0"}],
            dependencies=[{"agent_id": "a1", "depends_on": []}],
            stages=[["a1"]],
            revision_policy={"max_total_rounds": 1},
        )
        b = StructuralHashInput(
            agents=[{"agent_id": "a2", "role": "design", "version": "1.0.0"}],
            dependencies=[{"agent_id": "a2", "depends_on": []}],
            stages=[["a2"]],
            revision_policy={"max_total_rounds": 1},
        )
        assert compute_structure_hash(a) != compute_structure_hash(b)

    def test_depends_on_order_independent(self):
        a = StructuralHashInput(
            agents=[{"agent_id": "x", "role": "design", "version": "1.0.0"}],
            dependencies=[{"agent_id": "x", "depends_on": ["a", "b"]}],
            stages=[["x"]],
            revision_policy={"max_total_rounds": 1},
        )
        b = StructuralHashInput(
            agents=[{"agent_id": "x", "role": "design", "version": "1.0.0"}],
            dependencies=[{"agent_id": "x", "depends_on": ["b", "a"]}],
            stages=[["x"]],
            revision_policy={"max_total_rounds": 1},
        )
        assert compute_structure_hash(a) == compute_structure_hash(b)

    def test_frozenset_order_in_depends_on(self):
        inp = StructuralHashInput(
            agents=[{"agent_id": "x", "role": "design", "version": "1.0.0"}],
            dependencies=[{"agent_id": "x", "depends_on": ["a", "b"]}],
            stages=[["x"]],
            revision_policy={"max_total_rounds": 1},
        )
        inp2 = StructuralHashInput(
            agents=[{"agent_id": "x", "role": "design", "version": "1.0.0"}],
            dependencies=[{"agent_id": "x", "depends_on": ["b", "a"]}],
            stages=[["x"]],
            revision_policy={"max_total_rounds": 1},
        )
        assert compute_structure_hash(inp) == compute_structure_hash(inp2)

    def test_stage_order_invariant(self):
        inp = StructuralHashInput(
            agents=[
                {"agent_id": "a1", "role": "design", "version": "1.0.0"},
                {"agent_id": "a2", "role": "review", "version": "1.0.0"},
            ],
            dependencies=[
                {"agent_id": "a1", "depends_on": []},
                {"agent_id": "a2", "depends_on": ["a1"]},
            ],
            stages=[["a1", "a2"]],
            revision_policy={"max_total_rounds": 1},
        )
        inp2 = StructuralHashInput(
            agents=[
                {"agent_id": "a2", "role": "review", "version": "1.0.0"},
                {"agent_id": "a1", "role": "design", "version": "1.0.0"},
            ],
            dependencies=[
                {"agent_id": "a2", "depends_on": ["a1"]},
                {"agent_id": "a1", "depends_on": []},
            ],
            stages=[["a1", "a2"]],
            revision_policy={"max_total_rounds": 1},
        )
        assert compute_structure_hash(inp) == compute_structure_hash(inp2)


class TestSemanticBriefHash:
    def test_same_semantics_same_hash(self):
        briefs = [{"agent_id": "a1", "task_description": "do X"}]
        assert compute_semantic_brief_hash(briefs) == compute_semantic_brief_hash(briefs)

    def test_different_description_different_hash(self):
        assert compute_semantic_brief_hash(
            [{"agent_id": "a1", "task_description": "do X"}]
        ) != compute_semantic_brief_hash([{"agent_id": "a1", "task_description": "do Y"}])

    def test_agent_id_order_independent(self):
        a = compute_semantic_brief_hash(
            [
                {"agent_id": "a1", "task_description": "X"},
                {"agent_id": "a2", "task_description": "Y"},
            ]
        )
        b = compute_semantic_brief_hash(
            [
                {"agent_id": "a2", "task_description": "Y"},
                {"agent_id": "a1", "task_description": "X"},
            ]
        )
        assert a == b

    def test_excludes_extra_fields(self):
        a = compute_semantic_brief_hash(
            [
                {"agent_id": "a1", "task_description": "X", "provenance": "old"},
            ]
        )
        b = compute_semantic_brief_hash(
            [
                {"agent_id": "a1", "task_description": "X", "provenance": "new"},
            ]
        )
        assert a == b


class TestEffectivePlanHash:
    def test_identical_inputs_same_hash(self):
        h = compute_effective_plan_hash("abc", "def")
        assert h == compute_effective_plan_hash("abc", "def")

    def test_format_is_sha256_hex(self):
        result = compute_effective_plan_hash("abc", "def")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_different_structure_different_hash(self):
        assert compute_effective_plan_hash("abc", "def") != compute_effective_plan_hash(
            "xyz", "def"
        )

    def test_different_semantic_different_hash(self):
        assert compute_effective_plan_hash("abc", "def") != compute_effective_plan_hash(
            "abc", "ghi"
        )
