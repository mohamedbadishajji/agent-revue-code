import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sys
sys.stdout.reconfigure(line_buffering=True)
from app.analyzer import analyze_pr
from app.pr_approval import submit_review

print("=== Test REVUE-15/40 : Approbation/rejet automatique ===\n")

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

print("\n2️⃣ Soumission de la review automatique...")
action = submit_review(
    repo_name=repo_name,
    pr_number=pr_number,
    issues=result['issues']
)

print(f"\n🎉 Terminé ! Action effectuée : {action}")
