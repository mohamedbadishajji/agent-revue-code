import os
from dotenv import load_dotenv
from app.github_client import get_github_client

load_dotenv()

INSTALLATION_ID = int(os.getenv("GITHUB_INSTALLATION_ID"))

# Définition des labels avec leurs couleurs (format hex sans #)
LABEL_DEFINITIONS = {
    "security-critical": {
        "color": "B60205",
        "description": "Vulnérabilité de sécurité critique détectée",
    },
    "has-bugs": {"color": "D93F0B", "description": "Bugs détectés par l'agent IA"},
    "needs-refactor": {
        "color": "FBCA04",
        "description": "Code smells détectés — refactoring recommandé",
    },
    "approved-by-ai": {
        "color": "0E8A16",
        "description": "Aucun problème détecté par l'agent IA",
    },
    "major-issues": {"color": "5319E7", "description": "Plus de 5 problèmes détectés"},
}


def determine_labels(issues: list) -> list:
    """
    Détermine quels labels appliquer selon les problèmes détectés
    REVUE-14 : Implémenter le labeling automatique
    """
    labels = []

    if not issues:
        labels.append("approved-by-ai")
        return labels

    has_critical_security = any(
        issue.get("severity") == "critical" and issue.get("type") == "security"
        for issue in issues
    )
    has_high_bug = any(
        issue.get("severity") == "high" and issue.get("type") == "bug"
        for issue in issues
    )
    has_smells = any(
        issue.get("type")
        in ["bad_naming", "duplicate_code", "long_function", "magic_number"]
        for issue in issues
    )

    if has_critical_security:
        labels.append("security-critical")

    if has_high_bug:
        labels.append("has-bugs")

    if has_smells:
        labels.append("needs-refactor")

    if len(issues) > 5:
        labels.append("major-issues")

    return labels


def ensure_labels_exist(repo) -> None:
    """
    Crée les labels sur le repo s'ils n'existent pas déjà
    """
    existing_labels = {label.name for label in repo.get_labels()}

    for label_name, props in LABEL_DEFINITIONS.items():
        if label_name not in existing_labels:
            try:
                repo.create_label(
                    name=label_name,
                    color=props["color"],
                    description=props["description"],
                )
                print(f"   ✅ Label créé : {label_name}")
            except Exception as e:
                print(f"   ⚠️ Erreur création label {label_name} : {str(e)}")


def apply_labels(repo_name: str, pr_number: int, issues: list) -> list:
    """
    Applique automatiquement les labels sur la PR
    REVUE-14 : Implémenter le labeling automatique
    """
    try:
        client = get_github_client(INSTALLATION_ID)
        repo = client.get_repo(repo_name)
        pr = repo.get_pull(pr_number)

        print(f"\n🏷️  Application des labels automatiques...")

        # S'assurer que les labels existent sur le repo
        ensure_labels_exist(repo)

        # Déterminer quels labels appliquer
        labels_to_apply = determine_labels(issues)

        # Appliquer les labels
        pr.add_to_labels(*labels_to_apply)

        print(f"   ✅ Labels appliqués : {', '.join(labels_to_apply)}")
        return labels_to_apply

    except Exception as e:
        print(f"   ❌ Erreur application labels : {str(e)}")
        return []
