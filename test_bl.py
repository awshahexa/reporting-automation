import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from agents.sharepoint_manager import SubmitAgent

sa = SubmitAgent()
path = r"sharepoint_sim\Working\Sites Document\Submit (hot folder)\failed\BL_DFREE_ACC_20260611.pdf"
t0 = time.time()
r = sa.verify_document(path)
elapsed = time.time() - t0
print(f"BL_DFREE: passed={r['passed']} ({elapsed:.1f}s)")
for rr in r["rule_results"]:
    s = "PASS" if rr["passed"] else "FAIL"
    iss = rr["issues"][:3] if rr["issues"] else "ok"
    print(f"  [{s}] {rr['rule']}: {iss}")
print(f"All issues: {r['issues']}")
