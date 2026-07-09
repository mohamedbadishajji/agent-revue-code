import os
from dotenv import load_dotenv
from app.github_client import get_github_client

load_dotenv()

INSTALLATION_ID = int(os.getenv("GITHUB_INSTALLATION_ID"))

# Signature de l'agent pour identifier ses commentaires
AGENT_SIGNATURE = "Agent IA de Revue de Code — Smartovate LTD"


def get_existing_comments(repo_name: str, pr_number: int) -> list:
    """
    Récupère tous les commentaires existants sur la PR
    REVUE-23/50 : Vérification de l'historique
    """
    try:
        client = get_github_client(INSTALLATION_ID)
        repo = client.get_repo(repo_name)
        pr = repo.get_pull(pr_number)

        existing_comments = []

        # Récupérer les commentaires inline (review comments)
        for comment in pr.get_review_comments():
            if AGENT_SIGNATURE in comment.body:
                existing_comments.append(
                    {
                        "type": "inline",
                        "file_path": comment.path,
                        "line": comment.line,
                        "body": comment.body,
                        "id": comment.id,
                    }
                )

        # Récupérer les commentaires globaux (issue comments)
        for comment in pr.get_issue_comments():
            if AGENT_SIGNATURE in comment.body:
                existing_comments.append(
                    {
                        "type": "global",
                        "file_path": None,
                        "line": None,
                        "body": comment.body,
                        "id": comment.id,
                    }
                )

        print(f"   📋 {len(existing_comments)} commentaire(s) de l'agent déjà présents")
        return existing_comments

    except Exception as e:
        print(f"   ⚠️ Erreur récupération commentaires : {str(e)}")
        return []


def is_duplicate(issue: dict, existing_comments: list) -> bool:
    """
    Vérifie si un commentaire similaire existe déjà
    Compare : fichier + ligne + type de problème
    """
    file_path = issue.get("file_path")
    line = issue.get("line")
    issue_type = issue.get("type", "")
    severity = issue.get("severity", "")

    for comment in existing_comments:
        # Vérifier même fichier et même ligne
        if comment.get("file_path") == file_path and comment.get("line") == line:
            # Vérifier si le type de problème est mentionné dans le commentaire
            if (
                issue_type.lower() in comment["body"].lower()
                or severity.lower() in comment["body"].lower()
            ):
                return True

    return False


def filter_duplicate_issues(issues: list, repo_name: str, pr_number: int) -> list:
    """
    Filtre les issues déjà commentées sur la PR
    REVUE-23/50 : Éviter les commentaires dupliqués
    """
    if not issues:
        return []

    print(f"\n🔍 Vérification des doublons...")

    # Récupérer les commentaires existants
    existing_comments = get_existing_comments(repo_name, pr_number)

    if not existing_comments:
        print(f"   ✅ Aucun commentaire existant — toutes les issues seront postées")
        return issues

    # Filtrer les doublons
    new_issues = []
    duplicate_count = 0

    for issue in issues:
        if is_duplicate(issue, existing_comments):
            duplicate_count += 1
            print(
                f"   ⚠️ Doublon ignoré — {issue.get('file_path')} ligne {issue.get('line')} [{issue.get('type')}]"
            )
        else:
            new_issues.append(issue)

    print(f"   ✅ {len(new_issues)} nouvelle(s) issue(s) à poster")
    print(f"   🚫 {duplicate_count} doublon(s) ignoré(s)")

    return new_issues
