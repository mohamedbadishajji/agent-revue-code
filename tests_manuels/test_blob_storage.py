import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.dashboard import get_all_reports

reports = get_all_reports()
print(f"Nombre de rapports trouvés : {len(reports)}")
for r in reports:
    print(f"  - PR #{r['pr_number']} — {r['repo_name']}")
