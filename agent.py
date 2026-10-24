"""Mini gap-audit agent for ONE control: MFA for all users.

Principles: deterministic code decides outcomes; a human approves the report.
Stdlib only. Run: python agent.py --data data/mock_entra.json
"""
import argparse
import datetime as dt
import hashlib
import json
import time
from pathlib import Path

CONTROL = {
    "id": "MFA-ALL-USERS",
    "title": "MFA is enforced for all active users",
    # map once, reuse everywhere: one finding serves several frameworks
    "maps_to": {
        "ISO 27001:2022": "A.5.17, A.8.5",
        "SOC 2": "CC6.1",
        "NIS2": "Art. 21(2)(j)",
    },
}
MAX_EVIDENCE_AGE_DAYS, MAX_STEPS, PAGE_SIZE = 7, 50, 3


class TransientError(Exception):
    pass


class MockEntra:
    """Read-only stand-in for Microsoft Entra ID (real: Graph userRegistrationDetails)."""

    def __init__(self, path, fail_first=0):
        self.data, self.fails = json.loads(Path(path).read_text()), fail_first

    def fetch(self, cursor):
        if self.fails > 0:
            self.fails -= 1
            raise TransientError("429 Too Many Requests")
        u, n = self.data["users"], cursor + PAGE_SIZE
        return {
            "users": u[cursor:n],
            "next": n if n < len(u) else None,
            "generated_at": self.data["generated_at"],
        }


def check_user(u):  # pure, deterministic, easy to test and to explain to an auditor
    if not u["enabled"]:
        return "OUT_OF_SCOPE", "account disabled"
    if u["mfa"]:
        return "PASS", "MFA registered"
    if u["type"] in ("service", "breakglass"):
        if u.get("exemption"):
            return "EXEMPT", "documented exemption: " + u["exemption"]
        return "NEEDS_HUMAN", f"{u['type']} account has no documented exemption"
    return "GAP", "active member without MFA"


def summarize(results, age_days):
    pick = lambda s: sorted(r["upn"] for r in results if r["status"] == s)
    gaps, review = pick("GAP"), pick("NEEDS_HUMAN")
    if age_days > MAX_EVIDENCE_AGE_DAYS:
        status = "UNKNOWN"  # never claim MET on stale evidence
    elif gaps:
        status = "GAP"
    elif review:
        status = "NEEDS_HUMAN"
    else:
        status = "MET"
    return {"status": status, "gaps": gaps, "needs_human": review}


def audit_users(users, age_days):  # same logic the agent uses, reused by evals
    return summarize([dict(upn=u["upn"], status=check_user(u)[0]) for u in users], age_days)


def with_retry(fn, tries=3, base=0.05):
    for i in range(tries):
        try:
            return fn()
        except TransientError:
            if i == tries - 1:
                raise
            time.sleep(base * 2 ** i)


def run(source, state_dir, today=None, crash_after=None):
    d = Path(state_dir)
    d.mkdir(parents=True, exist_ok=True)
    cp, logf, last = d / "checkpoint.json", d / "audit_log.jsonl", d / "last_run.json"

    def log(event, **kw):  # append-only trail: what happened, when, on which evidence
        with logf.open("a") as f:
            f.write(
                json.dumps(
                    {"ts": dt.datetime.now().isoformat(timespec="seconds"), "event": event, **kw}
                )
                + "\n"
            )

    state = (
        json.loads(cp.read_text())
        if cp.exists()
        else {"cursor": 0, "results": [], "generated_at": None}
    )
    if cp.exists():
        log("resumed", cursor=state["cursor"])
    steps = 0
    while state["cursor"] is not None:
        steps += 1
        if steps > MAX_STEPS:
            log("halt", reason="step limit")
            raise RuntimeError("step limit reached")
        page = with_retry(lambda: source.fetch(state["cursor"]))
        state["generated_at"] = page["generated_at"]
        for u in page["users"]:
            s, why = check_user(u)
            state["results"].append({"upn": u["upn"], "status": s, "why": why})
        log(
            "page_checked",
            cursor=state["cursor"],
            users=len(page["users"]),
            evidence_sha=hashlib.sha256(json.dumps(page["users"], sort_keys=True).encode()).hexdigest()[:12],
        )
        state["cursor"] = page["next"]
        cp.write_text(json.dumps(state))  # checkpoint after every page
        if crash_after and steps == crash_after and state["cursor"] is not None:
            raise RuntimeError("simulated crash")
    today = today or dt.date.today()
    age = (today - dt.date.fromisoformat(state["generated_at"])).days
    rep = {
        "control": CONTROL["id"],
        "maps_to": CONTROL["maps_to"],
        "evidence_age_days": age,
        **summarize(state["results"], age),
        "approval": {"status": "pending", "by": None},
    }
    prev = json.loads(last.read_text())["gaps"] if last.exists() else []
    rep["new_gaps"] = sorted(set(rep["gaps"]) - set(prev))
    rep["resolved"] = sorted(set(prev) - set(rep["gaps"]))
    last.write_text(json.dumps(rep, indent=1))
    cp.unlink(missing_ok=True)
    log("audit_done", status=rep["status"], gaps=len(rep["gaps"]))
    return rep


def explain(rep):
    """Manager-facing summary built only from verified report fields."""
    return (
        f"{CONTROL['title']}: {rep['status']}. "
        f"Gaps: {', '.join(rep['gaps']) or 'none'}. "
        f"Needs a human decision: {', '.join(rep['needs_human']) or 'none'}. "
        f"New since last run: {', '.join(rep['new_gaps']) or 'none'}. "
        f"Resolved since last run: {', '.join(rep['resolved']) or 'none'}. "
        f"Approval: {rep['approval']['status']}."
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="data/mock_entra.json")
    p.add_argument("--state", default="state")
    p.add_argument("--fail-first", type=int, default=0, help="simulate N rate-limit errors")
    p.add_argument("--crash-after", type=int, help="simulate a crash after N pages")
    p.add_argument("--today", help="YYYY-MM-DD, for reproducible runs")
    a = p.parse_args()
    rep = run(
        MockEntra(a.data, a.fail_first),
        a.state,
        dt.date.fromisoformat(a.today) if a.today else None,
        a.crash_after,
    )
    print(json.dumps(rep, indent=1))
    print("\n" + explain(rep))
