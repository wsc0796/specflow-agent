# M6 Multi-Agent Readiness Audit

## Verdict

`changes-required` — the local M6 implementation is ahead of `origin/main` and
now passes lint/import integration, but it does not yet meet the frozen M6
end-to-end acceptance criteria.

## Verified fixes

- M6 A/B evaluation now lives in the installed `src/specflow/evaluation`
  namespace; pytest can import it under the project's `src/` layout.
- The accidental root-level Python package and a case containing an absolute
  private repository path were removed.
- Ruff issues in the current M6 worktree were resolved.

## Blocking implementation gaps

1. `runner_multi.run_multi_agent` currently plans and writes a manifest only;
   it does not invoke `MultiAgentScheduler` or the six registered agents.
2. No multi-agent artifact contract yet demonstrates structured handoffs,
   topology traces, bounded Review→Revision→Review, or revision-exhausted
   completion semantics.
3. The A/B module aggregates supplied scores, but does not run the legacy and
   multi-agent modes on the same input or produce evidence-backed comparison
   artifacts.
4. The M6 task specs/reports T-024 through T-032 have not been created, so the
   current code cannot be truthfully recorded as task-complete.

## Boundary decision

Do not push the eleven existing M6 commits as a completed milestone. The next
safe action is to freeze T-024 through T-032 task specs, then repair the runner
execution contract before claiming M6 execution capability.
