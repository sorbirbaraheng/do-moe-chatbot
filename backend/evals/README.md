# Intent/Routing Regression Eval

Run deterministic regression checks for intent routing + follow-up context guards.

## Command

```bash
python3 backend/evals/run_intent_routing_eval.py --verbose
```

## What it validates

- `ranking/filter/count` route guard param enrichment
- follow-up continuity via `last_active_query`
- district extraction edge-cases (`อำเภอไหน` should not become district=`ไหน`)

## Exit code

- `0` = all cases passed
- `1` = at least one case failed
