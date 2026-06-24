import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from agents.sharepoint_manager import SubmitAgent

sa = SubmitAgent()

# Quick test on BL (text-based, fast)
t0 = time.time()
r = sa.verify_document(r"sharepoint_sim\Working\Sites Document\Review\DGAN\CC\BL_DGAN_ACC_20260601.pdf")
elapsed = time.time() - t0
status = "PASS" if r["passed"] else "FAIL"
print(f"BL: {status} ({elapsed:.1f}s)")
for rr in r["rule_results"]:
    s = "PASS" if rr["passed"] else "FAIL"
    iss = rr["issues"][:1] if rr["issues"] else "ok"
    print(f"  [{s}] {rr['rule']}: {iss}")

# Verify quality_rules dict covers all expected doc types
expected = ["TSSR","SATP","PL","PO","DN","BL","MOP","SMR","CC","FT","PAC","PAF","FAF"]
actual = list(sa.quality_rules.keys())
missing = [k for k in expected if k not in actual]
extra = [k for k in actual if k not in expected]
print(f"\nExpected: {expected}")
print(f"Actual:   {actual}")
if missing: print(f"MISSING: {missing}")
if extra: print(f"EXTRA: {extra}")
if not missing and not extra: print("All doc types covered!")
