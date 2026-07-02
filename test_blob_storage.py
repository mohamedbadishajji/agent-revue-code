from app.dashboard import get_all_reports

reports = get_all_reports()
print(f"Nombre de rapports trouvés : {len(reports)}")
for r in reports:
    print(f"  - PR #{r['pr_number']} — {r['repo_name']}")