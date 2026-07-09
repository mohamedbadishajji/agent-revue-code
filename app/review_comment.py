import os
import re
from dotenv import load_dotenv
from app.github_client import get_github_client
from app.rate_limiter import check_rate_limit, batch_post_comments

load_dotenv()

INSTALLATION_ID = int(os.getenv("GITHUB_INSTALLATION_ID"))


def get_patch_position(patch: str, target_line: int) -> int:
    """
    Convertit un numéro de ligne en position dans le patch
    Bug 3 du cahier des charges : Désynchronisation des numéros de ligne
    """
    position = 0
    current_line = 0

    for line in patch.splitlines():
        position += 1

        if line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)
            if match:
                current_line = int(match.group(1)) - 1

        elif line.startswith("+") and not line.startswith("+++"):
            current_line += 1
            if current_line == target_line:
                return position

        elif not line.startswith("-"):
            current_line += 1

    return None


def format_comment(issue: dict) -> str:
    """
    Formate un commentaire avec la syntaxe GitHub Markdown
    REVUE-41 : Inclut la suggestion de code GitHub native si disponible
    """
    severity_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}

    emoji = severity_emoji.get(issue.get("severity", "low"), "⚪")
    severity = issue.get("severity", "unknown").upper()
    issue_type = issue.get("type", "unknown")
    description = issue.get("description", "")
    suggestion = issue.get("suggestion", "")
    fix_code = issue.get("fix_code", "")

    comment = f"""## {emoji} Agent IA — [{severity}] {issue_type}

**Problème détecté :**
{description}

**Explication :**
{suggestion}"""

    # REVUE-41 : Ajouter le bloc GitHub Suggestion si le code de fix existe
    if fix_code and fix_code.strip():
        comment += f"""

**Correction proposée (cliquez sur "Apply suggestion") :**
````suggestion
{fix_code}
```"""

    comment += """

---
*Commentaire généré automatiquement par l'Agent IA de Revue de Code — Smartovate LTD*"""

    return comment


def post_inline_comment(
    repo_name: str, pr_number: int, issue: dict, patch: str
) -> bool:
    """
    Poste un commentaire inline sur une ligne spécifique de la PR
    REVUE-12/39 : Publication des commentaires inline
    REVUE-20/47 : Mapping de ligne incorrect — version améliorée
    """
    try:

        client = get_github_client(INSTALLATION_ID)
        repo = client.get_repo(repo_name)
        pr = repo.get_pull(pr_number)

        # Vérifier si l'issue doit être postée en commentaire global
        if issue.get("use_global_comment"):
            return post_file_comment(repo_name, pr_number, issue)

        # Utiliser la position du patch si déjà calculée
        line_number = issue.get("line")
        patch_position = issue.get("patch_position")

        # Si pas de position → calculer
        if not patch_position:
            patch_position = get_patch_position(patch, line_number)

        if patch_position is None:
            print(f"   ⚠️ Ligne {line_number} introuvable → commentaire global")
            return post_file_comment(repo_name, pr_number, issue)

        # Formater le commentaire
        comment_body = format_comment(issue)

        # Ajouter note si ligne corrigée
        if issue.get("line_mapping_corrected"):
            comment_body += f"\n\n> **Note :** Commentaire repositionné à la ligne {line_number} (ligne originale non disponible)"

        # Poster le commentaire inline
        commit = list(pr.get_commits())[-1]
        pr.create_review_comment(
            body=comment_body,
            commit=commit,
            path=issue.get("file_path"),
            line=line_number,
            side="RIGHT",
        )

        print(f"   ✅ Commentaire posté — {issue['file_path']} ligne {line_number}")
        return True

    except Exception as e:
        print(f"   ❌ Erreur posting commentaire : {str(e)}")
        # Fallback → commentaire global
        return post_file_comment(repo_name, pr_number, issue)


def post_file_comment(repo_name: str, pr_number: int, issue: dict) -> bool:
    """
    Poste un commentaire général sur la PR quand le mapping de ligne échoue
    Fallback pour Bug 3
    """
    try:
        client = get_github_client(INSTALLATION_ID)
        repo = client.get_repo(repo_name)
        pr = repo.get_pull(pr_number)

        comment_body = format_comment(issue)
        comment_body += f"\n\n> **Note :** Problème détecté dans `{issue.get('file_path')}` ligne {issue.get('line')}"

        pr.create_issue_comment(comment_body)
        print(
            f"   ✅ Commentaire global posté pour {issue.get('file_path')} ligne {issue.get('line')}"
        )
        return True

    except Exception as e:
        print(f"   ❌ Erreur posting commentaire global : {str(e)}")
        return False


def post_global_summary(
    repo_name: str,
    pr_number: int,
    summary: str,
    total_issues: int,
    issues: list = None,
    scoring: dict = None,
    score_report: str = None,
) -> bool:
    """
    Poste le résumé global de l'analyse sur la PR
    REVUE-13 : Résumé global enrichi
    REVUE-36 : Avec score de sévérité
    """
    try:
        client = get_github_client(INSTALLATION_ID)
        repo = client.get_repo(repo_name)
        pr = repo.get_pull(pr_number)

        # Emoji selon le nombre de problèmes
        if total_issues == 0:
            status_emoji = "✅"
            status = "APPROUVÉ"
        elif total_issues <= 2:
            status_emoji = "⚠️"
            status = "À RÉVISER"
        else:
            status_emoji = "❌"
            status = "CHANGEMENTS REQUIS"

        # Tableau récapitulatif par sévérité
        severity_table = ""
        files_analyzed = set()
        if issues:
            severity_count = {"critical": 0, "high": 0, "medium": 0, "low": 0}
            for issue in issues:
                severity = issue.get("severity", "low")
                if severity in severity_count:
                    severity_count[severity] += 1
                files_analyzed.add(issue.get("file_path", "unknown"))

            severity_table = f"""
| Sévérité | Nombre |
|----------|--------|
| 🔴 Critical | {severity_count['critical']} |
| 🟠 High | {severity_count['high']} |
| 🟡 Medium | {severity_count['medium']} |
| 🟢 Low | {severity_count['low']} |
"""

        files_count = len(files_analyzed) if files_analyzed else "N/A"

        # Section score de sévérité
        score_section = ""
        if scoring and score_report:
            score_section = f"""
---

{score_report}
"""

        global_comment = f"""# {status_emoji} Revue de Code Automatique — {status}

**Analysé par :** Agent IA de Revue de Code — Smartovate LTD
**Fichiers analysés :** {files_count}
**Total problèmes détectés :** {total_issues}
{severity_table}
---

## Résumé

{summary}
{score_section}
---
*Cette revue a été générée automatiquement par AWS Bedrock (Claude Sonnet 4.6). Elle ne remplace pas une revue humaine.*"""

        pr.create_issue_comment(global_comment)
        print(f"✅ Résumé global avec score posté sur la PR #{pr_number}")
        return True

    except Exception as e:
        print(f"❌ Erreur posting résumé : {str(e)}")
        return False


def post_all_comments(
    repo_name: str, pr_number: int, analysis_result: dict, diff_files: list
) -> None:
    """
    Poste tous les commentaires et le résumé global
    REVUE-22 : Avec rate limiting et regroupement
    REVUE-23/50 : Avec vérification des doublons
    REVUE-36 : Avec score de sévérité
    """
    print(f"\n📝 Publication des commentaires sur la PR #{pr_number}...\n")

    issues = analysis_result.get("issues", [])
    summary = analysis_result.get("summary", "")
    total_issues = analysis_result.get("total_issues", 0)
    scoring = analysis_result.get("scoring")
    score_report = analysis_result.get("score_report")

    # Créer un dictionnaire patch par fichier
    patch_by_file = {f["file_path"]: f["patch"] for f in diff_files if "patch" in f}

    # Vérifier le rate limit avant de commencer
    from app.github_client import get_github_client
    from app.duplicate_checker import filter_duplicate_issues

    client = get_github_client(INSTALLATION_ID)
    check_rate_limit(client)

    # Filtrer les doublons (REVUE-23/50)
    issues = filter_duplicate_issues(issues, repo_name, pr_number)

    if not issues:
        print("✅ Aucune nouvelle issue à poster — tout était déjà commenté")
        post_global_summary(
            repo_name=repo_name,
            pr_number=pr_number,
            summary=summary,
            total_issues=total_issues,
            issues=issues,
            scoring=scoring,
            score_report=score_report,
        )
        return

    # Préparer les commentaires
    comments_to_post = []
    for issue in issues:
        file_path = issue.get("file_path")
        patch = patch_by_file.get(file_path, "")
        comments_to_post.append(
            {
                "repo_name": repo_name,
                "pr_number": pr_number,
                "issue": issue,
                "patch": patch,
            }
        )

    # Poster par lots avec rate limiting
    posted = batch_post_comments(
        post_func=post_inline_comment,
        comments=comments_to_post,
        batch_size=5,
        delay=0.5,
    )

    print(f"\n✅ {posted}/{len(issues)} commentaires postés")

    # Poster le résumé global avec score
    post_global_summary(
        repo_name=repo_name,
        pr_number=pr_number,
        summary=summary,
        total_issues=total_issues,
        issues=issues,
        scoring=scoring,
        score_report=score_report,
    )
