import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sys
sys.stdout.reconfigure(line_buffering=True)
from app.analyzer import analyze_pr
from app.diff_parser import extract_diff, parse_diff
from app.review_comment import post_all_comments

print("=== Test REVUE-12/39 : Poster commentaires inline ===\n")

repo_name = input("Nom du repo : ")
pr_number = int(input("Numéro de la PR : "))
pr_title = input("Titre de la PR : ")

# Étape 1 : Analyser la PR
print("\n1️⃣ Analyse de la PR...")
result = analyze_pr(
    repo_name=repo_name,
    pr_number=pr_number,
    pr_title=pr_title
)

print(f"\n✅ Analyse terminée — {result['total_issues']} problème(s) détecté(s)")

if result['total_issues'] == 0:
    print("⚠️ Aucun problème détecté — pas de commentaires à poster")
else:
    # Étape 2 : Récupérer les diffs pour le mapping des lignes
    print("\n2️⃣ Récupération des diffs pour mapping des lignes...")
    diff_files = extract_diff(repo_name, pr_number)
    parsed_files = parse_diff(diff_files)

    # Étape 3 : Poster les commentaires
    print("\n3️⃣ Publication des commentaires sur GitHub...")
    post_all_comments(
        repo_name=repo_name,
        pr_number=pr_number,
        analysis_result=result,
        diff_files=parsed_files
    )

print("\n🎉 Terminé !")
