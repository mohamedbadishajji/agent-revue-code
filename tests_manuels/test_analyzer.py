import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sys
sys.stdout.reconfigure(line_buffering=True)
from app.analyzer import analyze_pr

print("=== Test Analyse complète de PR ===\n")

# Saisie interactive
repo_name = input("Nom du repo (ex: mohamedbadishajji/test_agent_revue) : ")
pr_number = int(input("Numéro de la PR : "))
pr_title = input("Titre de la PR : ")
include_tests = input("Inclure les fichiers de test ? (o/n) : ").lower() == "o"

result = analyze_pr(
    repo_name=repo_name,
    pr_number=pr_number,
    pr_title=pr_title,
    include_tests=include_tests
)

print("\n=== Resultats ===")
print(f"PR #{result['pr_number']} — {result['repo_name']}")
print(f"Total problemes : {result['total_issues']}")

if result['issues']:
    print("\nProblemes detectes :")
    for issue in result['issues']:
        print(f"\n  [{issue['severity']}] {issue['file_path']} — ligne {issue['line']}")
        print(f"  Type : {issue['type']}")
        print(f"  Description : {issue['description']}")
        print(f"  Suggestion : {issue['suggestion']}")

print(f"\nResume global :\n{result['summary']}")
