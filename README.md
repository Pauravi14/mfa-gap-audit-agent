# MFA gap-audit agent (prototype)

A small agent I built after studying how [GetTeddy](https://getteddy.ai/) describes its **Evidence Agent** (pull MFA registration data from Entra ID) and **Gap Audit Agent** (check evidence against controls, compare with the last run, open tasks for gaps). This repo implements one slice of that flow for learning purposes, using only public product information—not GetTeddy’s internal architecture.

**Control:** MFA for all active users, mapped once to ISO 27001 A.5.17/A.8.5, SOC 2 CC6.1, and NIS2 Art. 21(2)(j).

## Run

```bash
python agent.py --today 2026-10-24
python agent.py --fail-first 2
python agent.py --crash-after 1 || python agent.py
python evals.py
```

- `--today` — fixed “as of” date for reproducible evidence-age checks  
- `--fail-first` — simulate rate limits (retries with backoff)  
- `--crash-after` — simulate a crash, then resume from `state/checkpoint.json`

## Design

- **Deterministic checks:** pass/fail/gap status comes from code only, so runs are reproducible and auditable.
- **Agent harness:** read-only evidence tool, retries, checkpoint after each page, step limit.
- **Stale evidence:** reports older than 7 days yield `UNKNOWN` (never `MET`).
- **Human in the loop:** undocumented service/break-glass accounts → `NEEDS_HUMAN`; each report starts with `approval: pending`.
- **Audit trail:** append-only `state/audit_log.jsonl` with a hash of the evidence per step.
- **Drift:** compares gaps to the previous run (`new_gaps`, `resolved`).
- **Evals:** nine golden cases; `evals.py` shares the same logic as the agent.

## Limits / next steps

Mock Entra data instead of Microsoft Graph; single control; CLI only; approval is a field on the report, not a workflow yet.

Planned: read-only Entra connector, more controls, named approver workflow.
