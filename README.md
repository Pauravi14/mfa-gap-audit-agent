# MFA gap-audit agent (prototype)

A small prototype of an **evidence** step (pull MFA registration data from a mock Entra ID source) and a **gap audit** step (check evidence against a control, compare with the last run, surface new and resolved gaps). One control, CLI-only, for learning agent harness patterns in compliance automation.

**Control:** MFA for all active users, mapped once to ISO 27001 A.5.17/A.8.5, SOC 2 CC6.1, and NIS2 Art. 21(2)(j).

Built with AI coding tools; I reviewed and tested the code.

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

## Sample output

First run with mock data (`python agent.py --today 2026-10-24`):

```json
{
  "control": "MFA-ALL-USERS",
  "maps_to": {
    "ISO 27001:2022": "A.5.17, A.8.5",
    "SOC 2": "CC6.1",
    "NIS2": "Art. 21(2)(j)"
  },
  "evidence_age_days": 4,
  "status": "GAP",
  "gaps": ["lena.vogt", "omar.said"],
  "needs_human": ["breakglass-admin"],
  "approval": { "status": "pending", "by": null },
  "new_gaps": ["lena.vogt", "omar.said"],
  "resolved": []
}
```

The CLI also prints a short manager summary from those fields (template text, no external API).

## Design

- **Deterministic checks:** pass/fail/gap status comes from code only, so runs are reproducible and auditable.
- **Agent harness:** read-only evidence tool, retries, checkpoint after each page, step limit.
- **Stale evidence:** reports older than 7 days yield `UNKNOWN` (never `MET`).
- **Human in the loop:** undocumented service/break-glass accounts → `NEEDS_HUMAN`; each report starts with `approval: pending`.
- **Audit trail:** append-only `state/audit_log.jsonl` with a hash of the evidence per step.
- **Drift:** compares gaps to the previous run (`new_gaps`, `resolved`).
- **Evals:** nine golden cases; `evals.py` shares the same logic as the agent and runs on every push via GitHub Actions.

## Limits / next steps

Mock Entra data instead of Microsoft Graph; single control; CLI only; approval is a field on the report, not a workflow yet.

Planned: read-only Entra connector, more controls, named approver workflow.
