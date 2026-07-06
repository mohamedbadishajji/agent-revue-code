import sys
sys.stdout.reconfigure(line_buffering=True)
from app.analyzer import analyze_pr
from app.quality_report import (
    generate_quality_report_markdown,
    generate_quality_report_json,
    save_quality_report
)

print("=== Test REVUE-42 : Rapports de qualité par PR ===\n")

repo_name = input("Nom du repo : ")
pr_number = int(input("Numéro de la PR : "))
pr_title = input("Titre de la PR : ")

print("\n1️⃣ Analyse de la PR...")
result = analyze_pr(
    repo_name=repo_name,
    pr_number=pr_number,
    pr_title=pr_title
)

print(f"\n✅ Analyse terminée — {result['total_issues']} problème(s) détecté(s)")

print("\n2️⃣ Génération du rapport Markdown...")
report_md = generate_quality_report_markdown(
    repo_name=repo_name,
    pr_number=pr_number,
    pr_title=pr_title,
    issues=result['issues'],
    scoring=result['scoring']
)
print("✅ Rapport Markdown généré")
print("\n" + "="*60)
print(report_md)
print("="*60)

print("\n3️⃣ Génération du rapport JSON...")
report_json = generate_quality_report_json(
    repo_name=repo_name,
    pr_number=pr_number,
    pr_title=pr_title,
    issues=result['issues'],
    scoring=result['scoring'],
    file_line_counts=result.get('file_line_counts', {})
)
print("✅ Rapport JSON généré")

print("\n4️⃣ Sauvegarde du rapport...")
filepath = save_quality_report(report_json)

print(f"\n🎉 Terminé ! Rapport sauvegardé : {filepath}")