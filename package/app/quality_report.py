import json
import os
from datetime import datetime
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

load_dotenv()


def get_file_metrics(issues: list) -> dict:
    """
    Calcule les métriques par fichier
    REVUE-42 : Rapports de qualité par PR
    """
    file_metrics = {}

    for issue in issues:
        file_path = issue.get("file_path", "unknown")
        severity = issue.get("severity", "low")

        if file_path not in file_metrics:
            file_metrics[file_path] = {
                "total_issues": 0,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
            }

        file_metrics[file_path]["total_issues"] += 1
        if severity in file_metrics[file_path]:
            file_metrics[file_path][severity] += 1

    return file_metrics


def get_type_metrics(issues: list) -> dict:
    """
    Calcule les métriques par type de problème
    """
    type_metrics = {}

    for issue in issues:
        issue_type = issue.get("type", "unknown")

        if issue_type not in type_metrics:
            type_metrics[issue_type] = 0
        type_metrics[issue_type] += 1

    return type_metrics


def get_worst_file(file_metrics: dict) -> tuple:
    """
    Identifie le fichier avec le plus de problèmes
    """
    if not file_metrics:
        return None, 0

    worst_file = max(file_metrics.items(), key=lambda x: x[1]["total_issues"])
    return worst_file[0], worst_file[1]["total_issues"]


def generate_quality_report_markdown(
    repo_name: str, pr_number: int, pr_title: str, issues: list, scoring: dict
) -> str:
    """
    Génère un rapport de qualité complet en Markdown
    REVUE-42 : Rapports de qualité par PR
    """
    file_metrics = get_file_metrics(issues)
    type_metrics = get_type_metrics(issues)
    worst_file, worst_count = get_worst_file(file_metrics)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report = f"""# 📊 Rapport de Qualité — PR #{pr_number}

**Repository :** {repo_name}
**Titre :** {pr_title}
**Date d'analyse :** {timestamp}
**Analysé par :** Agent IA de Revue de Code — Smartovate LTD

---

## 🎯 Score Global

**Score : {scoring['score']}/100** — {scoring['risk_level']['emoji']} {scoring['risk_level']['level']}

_{scoring['risk_level']['description']}_

---

## 📁 Métriques par Fichier

| Fichier | Total | Critical | High | Medium | Low |
|---------|-------|----------|------|--------|-----|"""

    for file_path, metrics in file_metrics.items():
        report += f"\n| {file_path} | {metrics['total_issues']} | {metrics['critical']} | {metrics['high']} | {metrics['medium']} | {metrics['low']} |"

    if worst_file:
        report += f"\n\n⚠️ **Fichier le plus problématique :** `{worst_file}` ({worst_count} problème(s))"

    report += f"""

---

## 🏷️ Répartition par Type

| Type | Nombre |
|------|--------|"""

    for issue_type, count in type_metrics.items():
        report += f"\n| {issue_type} | {count} |"

    report += f"""

---

## 📋 Détail des Problèmes

"""

    if not issues:
        report += "✅ Aucun problème détecté.\n"
    else:
        for i, issue in enumerate(issues, 1):
            severity_emoji = {
                "critical": "🔴",
                "high": "🟠",
                "medium": "🟡",
                "low": "🟢",
            }
            emoji = severity_emoji.get(issue.get("severity", "low"), "⚪")

            report += f"""### {i}. {emoji} {issue.get('description', 'N/A')}

- **Fichier :** `{issue.get('file_path', 'N/A')}`
- **Ligne :** {issue.get('line', 'N/A')}
- **Sévérité :** {issue.get('severity', 'N/A')}
- **Type :** {issue.get('type', 'N/A')}
- **Suggestion :** {issue.get('suggestion', 'N/A')}

"""

    report += f"""---
_Rapport généré automatiquement le {timestamp} par l'Agent IA de Revue de Code._"""

    return report


def generate_quality_report_json(
    repo_name: str,
    pr_number: int,
    pr_title: str,
    issues: list,
    scoring: dict,
    file_line_counts: dict = None,
) -> dict:
    """
    Génère un rapport de qualité au format JSON
    Pour intégration future avec dashboard (REVUE-46)
    Inclut le nombre exact de lignes par fichier (pour temps gagne precis)
    """
    file_metrics = get_file_metrics(issues)
    type_metrics = get_type_metrics(issues)
    worst_file, worst_count = get_worst_file(file_metrics)

    return {
        "repo_name": repo_name,
        "pr_number": pr_number,
        "pr_title": pr_title,
        "analyzed_at": datetime.now().isoformat(),
        "score": scoring["score"],
        "risk_level": scoring["risk_level"]["level"],
        "total_issues": len(issues),
        "file_metrics": file_metrics,
        "type_metrics": type_metrics,
        "worst_file": (
            {"path": worst_file, "issue_count": worst_count} if worst_file else None
        ),
        "issues": issues,
        "file_line_counts": file_line_counts or {},
    }


def get_blob_service_client():
    """
    Crée le client Azure Blob Storage si les credentials sont configurés
    Retourne None si non configuré (fallback vers stockage local)
    """
    account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
    account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")

    if not account_name or not account_key:
        return None

    connection_string = (
        f"DefaultEndpointsProtocol=https;"
        f"AccountName={account_name};"
        f"AccountKey={account_key};"
        f"EndpointSuffix=core.windows.net"
    )

    try:
        return BlobServiceClient.from_connection_string(connection_string)
    except Exception as e:
        print(f"   ⚠️ Erreur connexion Azure Blob Storage : {str(e)}")
        return None


def save_quality_report(report_json: dict, output_dir: str = "reports") -> str:
    """
    Sauvegarde le rapport JSON
    REVUE-46 : Utilise Azure Blob Storage pour la persistance
    Fallback vers stockage local si Azure non configuré (dev local)
    """
    pr_number = report_json["pr_number"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"pr_{pr_number}_report_{timestamp}.json"

    json_content = json.dumps(report_json, indent=2, ensure_ascii=False)

    # Priorité 1 : Azure Blob Storage (persistant, production)
    blob_service = get_blob_service_client()
    if blob_service:
        try:
            container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "reports")
            blob_client = blob_service.get_blob_client(
                container=container_name, blob=filename
            )
            blob_client.upload_blob(json_content, overwrite=True)
            print(f"   ✅ Rapport sauvegardé sur Azure Blob Storage : {filename}")
            return f"blob://{container_name}/{filename}"
        except Exception as e:
            print(f"   ⚠️ Erreur sauvegarde Azure Blob : {str(e)} — fallback local")

    # Priorité 2 : Stockage local (développement)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    local_path = f"{output_dir}/{filename}"
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(json_content)

    print(f"   ✅ Rapport sauvegardé localement : {local_path}")
    return local_path
