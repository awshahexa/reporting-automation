import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from agents.sharepoint_manager import SubmitAgent

path = r"sharepoint_sim\Working\Sites Document\Submit (hot folder)\failed\BL_DFREE_ACC_20260611.pdf"

# Test signature rule directly
passed, issues = SubmitAgent._rule_has_signature(path)
print(f"_rule_has_signature(full): passed={passed}")
for i in issues:
    print(f"  {i}")

# Test signature rule last page only
passed2, issues2 = SubmitAgent._rule_has_signature(path, last_page_only=True)
print(f"\n_rule_has_signature(last_page): passed={passed2}")
for i in issues2:
    print(f"  {i}")
