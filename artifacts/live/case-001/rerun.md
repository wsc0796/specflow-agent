# Rerun Template (Phase 4B/4C)

```bash
# 1. checkout frozen commit
git checkout bc76214

# 2. provider env (after user approval only)
export SPECFLOW_LLM_BASE_URL=...        # PENDING_USER_APPROVAL
export SPECFLOW_LLM_API_KEY=...         # PENDING_USER_APPROVAL (never log)
export SPECFLOW_LLM_MODEL=...           # PENDING_USER_APPROVAL

# 3. run live case
uv run specflow run \
  --repo <case-repository-path> \
  --requirement "$(cat artifacts/live/case-001/request.json)" \
  --provider openai-compatible \
  --mode multi-agent \
  --output artifacts/live/case-001/run

# 4. Phase 4C audit checklist (independent window)
# - artifacts from the frozen commit; brief consumed; findings/revision traceable
# - provider attempts/token counts complete; token never wrongly 0
# - hashes recomputable; trace/manifest consistent; no secrets; no manual edits
```

Do not run until the user approves API key, model, max cost, max token, and max wall-clock.
