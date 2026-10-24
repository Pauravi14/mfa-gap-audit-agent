"""Golden-set regression evals. Run in CI: python evals.py (exit code 1 on any failure)."""
import sys

from agent import audit_users


def m(upn, mfa=True, enabled=True):
    return dict(upn=upn, type="member", enabled=enabled, mfa=mfa)


def s(upn, **kw):
    return dict(upn=upn, type=kw.pop("type", "service"), enabled=True, mfa=False, **kw)


CASES = [  # (name, users, evidence_age_days, expected_status, expected_gaps)
    ("all members have MFA", [m("a"), m("b")], 1, "MET", []),
    ("one member without MFA", [m("a"), m("b", mfa=False)], 1, "GAP", ["b"]),
    ("disabled user is out of scope", [m("a"), m("old", mfa=False, enabled=False)], 1, "MET", []),
    ("service account with exemption", [m("a"), s("svc", exemption="POL-12")], 1, "MET", []),
    ("service account, no exemption -> human", [m("a"), s("svc")], 1, "NEEDS_HUMAN", []),
    ("break-glass, no exemption -> human", [m("a"), s("bg", type="breakglass")], 1, "NEEDS_HUMAN", []),
    ("stale evidence is never MET", [m("a"), m("b")], 10, "UNKNOWN", []),
    ("stale evidence still lists gaps", [m("a", mfa=False)], 10, "UNKNOWN", ["a"]),
    ("gap wins over human review", [m("a", mfa=False), s("svc")], 1, "GAP", ["a"]),
]

fails = 0
for name, users, age, want, want_gaps in CASES:
    got = audit_users(users, age)
    ok = got["status"] == want and got["gaps"] == want_gaps
    fails += not ok
    print(
        ("PASS " if ok else "FAIL ")
        + name
        + ("" if ok else f"  expected {want} {want_gaps}, got {got['status']} {got['gaps']}")
    )
print(f"\n{len(CASES) - fails}/{len(CASES)} passed")
sys.exit(1 if fails else 0)
