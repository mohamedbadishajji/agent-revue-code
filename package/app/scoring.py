import os
from dotenv import load_dotenv

load_dotenv()

# ══════════════════════════════════════════════
# REVUE-36 : Système de scoring de sévérité
# ══════════════════════════════════════════════

# Points de base par sévérité
SEVERITY_BASE_POINTS = {
    "critical": 10,
    "high": 5,
    "medium": 2,
    "low": 1
}

# Multiplicateurs par type de problème
TYPE_MULTIPLIERS = {
    "security": 2.0,      # Sécurité → double les points
    "bug": 1.5,           # Bug → augmente de 50%
    "logic": 1.2,         # Logique → augmente de 20%
    "performance": 1.0,   # Performance → points normaux
    "style": 0.5,         # Style → réduit de 50%
    "unknown": 1.0        # Inconnu → points normaux
}

# Bonus OWASP pour les vulnérabilités documentées
OWASP_BONUS = 3

# Niveaux de risque selon le score
RISK_LEVELS = [
    (90, 100, "CLEAN", "✅", "Aucun problème significatif détecté"),
    (70, 89, "LOW RISK", "🟢", "Quelques problèmes mineurs à corriger"),
    (50, 69, "MEDIUM RISK", "🟡", "Problèmes importants à corriger avant merge"),
    (30, 49, "HIGH RISK", "🟠", "Problèmes critiques — révision approfondie requise"),
    (0, 29, "CRITICAL RISK", "🔴", "Vulnérabilités critiques — ne pas merger"),
]


def calculate_issue_points(issue: dict) -> float:
    """
    Calcule les points d'une issue selon sa sévérité, type et contexte
    Logique intelligente et contextuelle
    """
    severity = issue.get("severity", "low").lower()
    issue_type = issue.get("type", "unknown").lower()

    # Points de base selon la sévérité
    base_points = SEVERITY_BASE_POINTS.get(severity, 1)

    # Multiplicateur selon le type
    multiplier = TYPE_MULTIPLIERS.get(issue_type, 1.0)

    # Bonus OWASP si vulnérabilité documentée
    owasp_bonus = 0
    if issue.get("owasp") or (issue_type == "security" and severity in ["critical", "high"]):
        owasp_bonus = OWASP_BONUS

    # Calcul final
    points = (base_points * multiplier) + owasp_bonus

    return round(points, 2)


def get_risk_level(score: int) -> dict:
    """
    Détermine le niveau de risque selon le score
    """
    for min_score, max_score, level, emoji, description in RISK_LEVELS:
        if min_score <= score <= max_score:
            return {
                "level": level,
                "emoji": emoji,
                "description": description
            }
    return {"level": "CRITICAL RISK", "emoji": "🔴", "description": "Risque critique"}


def calculate_severity_score(issues: list) -> dict:
    """
    Calcule le score de sévérité complet pour une liste d'issues
    REVUE-36 : Système de scoring intelligent et contextuel
    """
    if not issues:
        return {
            "score": 100,
            "total_points": 0,
            "risk_level": get_risk_level(100),
            "breakdown": {
                "critical": {"count": 0, "points": 0},
                "high": {"count": 0, "points": 0},
                "medium": {"count": 0, "points": 0},
                "low": {"count": 0, "points": 0}
            },
            "by_type": {},
            "total_issues": 0
        }

    # Calcul des points par issue
    total_points = 0
    breakdown = {
        "critical": {"count": 0, "points": 0},
        "high": {"count": 0, "points": 0},
        "medium": {"count": 0, "points": 0},
        "low": {"count": 0, "points": 0}
    }
    by_type = {}

    for issue in issues:
        severity = issue.get("severity", "low").lower()
        issue_type = issue.get("type", "unknown").lower()
        points = calculate_issue_points(issue)

        total_points += points

        # Breakdown par sévérité
        if severity in breakdown:
            breakdown[severity]["count"] += 1
            breakdown[severity]["points"] += points

        # Breakdown par type
        if issue_type not in by_type:
            by_type[issue_type] = {"count": 0, "points": 0}
        by_type[issue_type]["count"] += 1
        by_type[issue_type]["points"] += points

    # Score final (0-100)
    score = max(0, int(100 - total_points))
    risk = get_risk_level(score)

    return {
        "score": score,
        "total_points": round(total_points, 2),
        "risk_level": risk,
        "breakdown": breakdown,
        "by_type": by_type,
        "total_issues": len(issues)
    }


def generate_score_report(issues: list, repo_name: str, pr_number: int) -> str:
    """
    Génère un rapport de scoring formaté en Markdown
    pour publication sur GitHub
    """
    scoring = calculate_severity_score(issues)
    score = scoring["score"]
    risk = scoring["risk_level"]
    breakdown = scoring["breakdown"]
    by_type = scoring["by_type"]

    report = f"""## {risk['emoji']} Score de Risque — {risk['level']}

**Score global : {score}/100**
_{risk['description']}_

### Détail par sévérité

| Sévérité | Nombre | Points déduits |
|----------|--------|----------------|
| 🔴 Critical | {breakdown['critical']['count']} | {round(breakdown['critical']['points'], 1)} pts |
| 🟠 High | {breakdown['high']['count']} | {round(breakdown['high']['points'], 1)} pts |
| 🟡 Medium | {breakdown['medium']['count']} | {round(breakdown['medium']['points'], 1)} pts |
| 🟢 Low | {breakdown['low']['count']} | {round(breakdown['low']['points'], 1)} pts |
| **Total** | **{scoring['total_issues']}** | **{scoring['total_points']} pts** |

### Détail par type de problème

| Type | Nombre | Points |
|------|--------|--------|"""

    for issue_type, data in by_type.items():
        report += f"\n| {issue_type} | {data['count']} | {round(data['points'], 1)} pts |"

    report += f"""

---
_Score calculé automatiquement par l'Agent IA — Smartovate LTD_
_Formule : Score = max(0, 100 - Σ(points × multiplicateur_type + bonus_OWASP))_"""

    return report