Create a task specification for SpecFlow Agent.

Project context:

{{ project_context }}

User requirement:

{{ user_requirement }}

Requirement analysis:

{{ requirement_analysis }}

Return strict JSON with exactly these fields:

- requirement_summary: string
- proposed_solution: string
- architecture_or_design: string
- affected_components: array of strings
- implementation_steps: array of strings
- api_or_data_changes: array of strings
- test_plan: array of strings
- risks: array of strings
- acceptance_criteria_mapping: array of objects with criterion and implementation
- analysis_hash: string
- requires_review: boolean
- degraded: boolean

Do not include prose outside the JSON object.
