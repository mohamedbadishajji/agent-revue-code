import os
from dotenv import load_dotenv
from app.github_client import get_github_client

load_dotenv()

INSTALLATION_ID = int(os.getenv("GITHUB_INSTALLATION_ID"))


def determine_review_action(issues: list) -> str:
    """
    Détermine l'action de review selon les problèmes détectés
    REVUE-15/40 : Approbation/rejet automatique des PRs

    IMPORTANT : Ne fait JAMAIS d'auto-merge (exclu du cahier des charges)
    Seulement soumet une review (approve/request changes/comment)
    """
    if not issues:
        return "APPROVE"

    has_critical = any(issue.get("severity") == "critical" for issue in issues)
    has_high = any(issue.get("severity") == "high" for issue in issues)

    if has_critical or has_high:
        return "REQUEST_CHANGES"

    # Seulement medium/low → juste un commentaire, pas de blocage
    return "COMMENT"


def build_review_message(action: str, issues: list) -> str:
    """
    Construit le message accompagnant la review
    """
    total = len(issues)
    critical_count = sum(1 for i in issues if i.get("severity") == "critical")
    high_count = sum(1 for i in issues if i.get("severity") == "high")

    if action == "APPROVE":
        return "✅ Aucun problème détecté par l'analyse automatique. Code approuvé par l'Agent IA."

    elif action == "REQUEST_CHANGES":
        return f"""❌ Cette PR nécessite des changements avant d'être mergée.

**{critical_count} problème(s) critique(s)** et **{high_count} problème(s) élevé(s)** détectés.

Merci de corriger les points soulevés dans les commentaires inline avant de soumettre à nouveau cette PR pour revue."""

    else:  # COMMENT
        return f"""💬 Quelques points d'amélioration mineurs ont été détectés ({total} au total).

Ces problèmes ne bloquent pas la PR mais nous recommandons de les corriger pour améliorer la qualité du code."""


def submit_review(repo_name: str, pr_number: int, issues: list) -> str:
    """
    Soumet une review automatique sur la PR
    NE FAIT JAMAIS D'AUTO-MERGE — uniquement approve/request_changes/comment
    """
    try:
        client = get_github_client(INSTALLATION_ID)
        repo = client.get_repo(repo_name)
        pr = repo.get_pull(pr_number)

        action = determine_review_action(issues)
        message = build_review_message(action, issues)

        print(f"\n🔍 Soumission de la review automatique...")
        print(f"   Action déterminée : {action}")

        pr.create_review(
            body=message,
            event=action
        )

        print(f"   ✅ Review soumise avec succès : {action}")
        return action

    except Exception as e:
        print(f"   ❌ Erreur soumission review : {str(e)}")
        return None