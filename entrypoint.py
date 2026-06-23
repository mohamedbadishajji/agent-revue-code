import sys
import argparse
import os
from dotenv import load_dotenv

load_dotenv()


def main():
    """
    Point d'entrée principal pour GitHub Action
    REVUE-19 : Publier comme GitHub Action réutilisable
    """
    parser = argparse.ArgumentParser(description="Agent IA de Revue de Code")
    parser.add_argument("--repo", required=True, help="Nom du repository (owner/repo)")
    parser.add_argument("--pr", required=True, type=int, help="Numéro de la PR")
    parser.add_argument("--title", required=True, help="Titre de la PR")
    parser.add_argument("--include-tests", default="false", help="Inclure les fichiers de test")

    args = parser.parse_args()

    include_tests = args.include_tests.lower() == "true"

    print(f"\n Agent IA de Revue de Code — Smartovate LTD")
    print(f"📋 Repo : {args.repo}")
    print(f"📋 PR : #{args.pr} — {args.title}")
    print(f"📋 Include tests : {include_tests}\n")

    # Import des modules de l'agent
    from app.analyzer import analyze_pr
    from app.diff_parser import extract_diff, parse_diff
    from app.review_comment import post_all_comments
    from app.pr_labeler import apply_labels
    from app.pr_approval import submit_review

    # Étape 1 : Analyser la PR
    print("1️⃣ Analyse de la PR avec AWS Bedrock...")
    result = analyze_pr(
        repo_name=args.repo,
        pr_number=args.pr,
        pr_title=args.title,
        include_tests=include_tests
    )

    print(f"\n✅ Analyse terminée — {result['total_issues']} problème(s) détecté(s)")

    # Étape 2 : Récupérer les diffs pour le mapping des lignes
    print("\n2️⃣ Récupération des diffs...")
    diff_files = extract_diff(args.repo, args.pr)
    parsed_files = parse_diff(diff_files)

    # Étape 3 : Poster les commentaires
    print("\n3️⃣ Publication des commentaires sur GitHub...")
    post_all_comments(
        repo_name=args.repo,
        pr_number=args.pr,
        analysis_result=result,
        diff_files=parsed_files
    )

    # Étape 4 : Appliquer les labels
    print("\n4️⃣ Application des labels automatiques...")
    labels = apply_labels(
        repo_name=args.repo,
        pr_number=args.pr,
        issues=result['issues']
    )

    # Étape 5 : Soumettre la review
    print("\n5️⃣ Soumission de la review automatique...")
    action = submit_review(
        repo_name=args.repo,
        pr_number=args.pr,
        issues=result['issues']
    )

    # Outputs pour GitHub Actions
    with open(os.environ.get("GITHUB_OUTPUT", "/dev/null"), "a") as f:
        f.write(f"total_issues={result['total_issues']}\n")
        f.write(f"review_action={action}\n")

    print(f"\n Agent IA terminé avec succès !")
    print(f"   Total problèmes : {result['total_issues']}")
    print(f"   Action review : {action}")
    print(f"   Labels : {', '.join(labels)}")

    # Exit code selon les problèmes détectés
    if action == "REQUEST_CHANGES":
        sys.exit(1)  # Echec → bloque le merge
    else:
        sys.exit(0)  # Succès


if __name__ == "__main__":
    main()