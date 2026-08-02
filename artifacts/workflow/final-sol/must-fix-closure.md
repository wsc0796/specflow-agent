# MUST_FIX Closure

| Finding | Closure | Evidence |
| --- | --- | --- |
| stale FAILED manifest snapshots | terminal current snapshot + trigger snapshot | CLI failure regression, `0d4816a` |
| retry reserve ignored | retry identity and separate total limit | reserve boundary tests, `0d4816a` |
| standalone guarded calls classified mock/bypassed | live compatibility guard and AST gate | runtime/adapter/enricher tests, `0d4816a` |
| default mock provider classified live | one effective mock decision | CLI manifest regression, `0d4816a` |
| mixed token totals presented complete | nullable aggregate + known subtotals | token tests, `0d4816a` |
| failure envelopes counted completed | result-aware agent settlement | failed manifest regression, `0d4816a` |
| explicit alias conflicts accepted | omitted-vs-explicit initialization | calibration tests, `0d4816a` |
| unsupported MCP negotiation/lifecycle bypass | explicit state machine and server version | unit + subprocess tests, `06b1cf2` |
| Pilot gold leakage/empty legacy candidates | requirement-only single + native legacy derivation | 15-run smoke, `06b1cf2` |
| blind IDs decoded from source index/seed | post-shuffle IDs; seed withheld | blind-pack tests, `06b1cf2` |
| tracked secret/path/debug evidence gaps | full tracked scan, path redaction, debug removal | secret tests and scan, `06b1cf2` |

No reproduced MUST_FIX remains open at the verified code commit. External cost and
protocol blockers remain and cannot be closed by code changes alone.
