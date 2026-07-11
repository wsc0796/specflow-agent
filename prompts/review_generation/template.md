Review SpecFlow Agent's generated implementation plan.

Project context:

{{ project_context }}

User requirement:

{{ user_requirement }}

Requirement analysis:

{{ requirement_analysis }}

Generation output:

{{ generation_output }}

Return strict JSON with exactly these fields:

- decision: PASS or REJECT
- summary: string
- issues: array of objects with code, severity, message, related_requirement, suggestion
- missing_requirements: array of strings
- risk_findings: array of strings
- acceptance_criteria_results: array of objects with criterion, passed, notes
- severity: info, low, medium, high, or critical
- requires_revision: boolean
- requires_human_review: boolean
- analysis_hash: string
- generation_hash: string
- degraded: boolean

Do not include prose outside the JSON object.
