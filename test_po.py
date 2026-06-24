import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from agents.sharepoint_manager import SubmitAgent

sa = SubmitAgent()
t0 = time.time()
r = sa.verify_document(r"failed\PO_DFREE_ACC_20260611.pdf")
elapsed = time.time() - t0
print(f"PO_DFREE: passed={r['passed']} ({elapsed:.1f}s)")
for rr in r["rule_results"]:
    s = "PASS" if rr["passed"] else "FAIL"
    iss = rr["issues"][:3] if rr["issues"] else "ok"
    print(f"  [{s}] {rr['rule']}: {iss}")
print(f"All issues: {r['issues']}")
