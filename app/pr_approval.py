import os
from dotenv import load_dotenv
from app.github_client import get_github_client

load_dotenv()

INSTALLATION_ID = int(os.getenv("GITHUB_INSTALLATION_ID"))


def determine_review_action(issues: list, severity_threshold: str = "high") -> str:
    """
    Détermine l'action de review selon les problèmes détectés
    REVUE-15 : Logique générale (sévérité)
    REVUE-40 : Logique stricte axée sécurité — approuve si pas de faille critique
    REVUE-45 : Utilise le severity_threshold configuré par le repository

    IMPORTANT : Ne fait JAMAIS d'auto-merge (exclu du cahier des charges)
    Seulement soumet une review (approve/request changes/comment)
    """
    if not issues:
        return "APPROVE"

    # Ordre de sévérité pour comparaison
    severity_order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    threshold_level = severity_order.get(severity_threshold, 3)

    # REVUE-40 : Bloquer immédiatement si UNE SEULE faille de sécurité
    # atteint ou dépasse le seuil configuré
    has_security_issue = any(
        issue.get("type") == "security"
        and severity_order.get(issue.get("severity", "low"), 1) >= threshold_level
        for issue in issues
    )

    if has_security_issue:
        return "REQUEST_CHANGES"

    # Bugs non liés à la sécurité qui atteignent le seuil configuré
    has_blocking_bug = any(
        issue.get("type") != "security"
        and severity_order.get(issue.get("severity", "low"), 1) >= threshold_level
        for issue in issues
    )

    if has_blocking_bug:
        return "REQUEST_CHANGES"

    # Sous le seuil → commentaire informatif seulement
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
    REVUE-45 : Utilise la configuration personnalisée du repo
    NE FAIT JAMAIS D'AUTO-MERGE — uniquement approve/request_changes/comment
    """
    try:
        from app.config_loader import load_repo_config

        client = get_github_client(INSTALLATION_ID)
        repo = client.get_repo(repo_name)
        pr = repo.get_pull(pr_number)

        # Charger la configuration personnalisée (REVUE-45)
        config = load_repo_config(repo_name)
        severity_threshold = config.get("severity_threshold", "high")

        action = determine_review_action(issues, severity_threshold)
        message = build_review_message(action, issues)

        print(f"\n🔍 Soumission de la review automatique...")
        print(f"   Seuil configuré : {severity_threshold}")
        print(f"   Action déterminée : {action}")

        pr.create_review(body=message, event=action)

        print(f"   ✅ Review soumise avec succès : {action}")
        return action

    except Exception as e:
        print(f"   ❌ Erreur soumission review : {str(e)}")
        return None
