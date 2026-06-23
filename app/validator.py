import re
import os
from dotenv import load_dotenv

load_dotenv()

# Mots vagues qui indiquent une hallucination potentielle
VAGUE_KEYWORDS = [
    "pourrait", "peut-être", "possible", "potentiellement",
    "il semble", "on dirait", "probablement", "éventuellement",
    "could", "might", "perhaps", "possibly", "seems like"
]

# Longueur minimale d'une description valide
MIN_DESCRIPTION_LENGTH = 20


def get_lines_in_patch(patch: str) -> set:
    """
    Extrait tous les numéros de lignes ajoutées dans le patch
    Pour vérifier que le LLM ne cite pas des lignes inexistantes
    """
    lines = set()
    current_line = 0

    for line in patch.splitlines():
        if line.startswith("@@"):
            match = re.search(r'\+(\d+)', line)
            if match:
                current_line = int(match.group(1)) - 1

        elif line.startswith("+") and not line.startswith("+++"):
            current_line += 1
            lines.add(current_line)

        elif not line.startswith("-"):
            current_line += 1

    return lines


def get_functions_in_patch(patch: str) -> set:
    """
    Extrait les noms de fonctions définies dans le patch
    Pour vérifier que le LLM ne cite pas des fonctions inexistantes
    """
    functions = set()

    for line in patch.splitlines():
        if line.startswith("+"):
            # Python
            match = re.search(r'def\s+(\w+)\s*\(', line)
            if match:
                functions.add(match.group(1))

            # JavaScript
            match = re.search(r'function\s+(\w+)\s*\(', line)
            if match:
                functions.add(match.group(1))

            # Arrow function
            match = re.search(r'const\s+(\w+)\s*=\s*\(', line)
            if match:
                functions.add(match.group(1))

    return functions


def is_vague_description(description: str) -> bool:
    """
    Vérifie si une description est trop vague — signe d'hallucination
    """
    if len(description) < MIN_DESCRIPTION_LENGTH:
        return True

    description_lower = description.lower()
    vague_count = sum(1 for keyword in VAGUE_KEYWORDS if keyword in description_lower)

    # Si plus de 2 mots vagues → probablement une hallucination
    return vague_count >= 2


def validate_issue(issue: dict, patch: str) -> tuple:
    """
    Valide une issue détectée par le LLM
    Retourne (is_valid, reason)
    """
    line = issue.get("line")
    description = issue.get("description", "")

    # Validation 1 : Numéro de ligne valide
    valid_lines = get_lines_in_patch(patch)
    if line and valid_lines and line not in valid_lines:
        return False, f"Ligne {line} introuvable dans le diff (hallucination potentielle)"

    # Validation 2 : Description pas trop vague
    if is_vague_description(description):
        return False, f"Description trop vague : '{description[:50]}...'"

    # Validation 3 : Description pas trop courte
    if len(description) < MIN_DESCRIPTION_LENGTH:
        return False, f"Description trop courte : '{description}'"

    return True, "Issue valide"


def validate_issues(issues: list, patch: str) -> list:
    """
    Filtre les hallucinations du LLM
    REVUE-21 : Validation post-LLM
    """
    if not issues:
        return []

    valid_issues = []
    rejected_count = 0

    print(f"\n🔍 Validation post-LLM de {len(issues)} issue(s)...")

    for issue in issues:
        is_valid, reason = validate_issue(issue, patch)

        if is_valid:
            valid_issues.append(issue)
        else:
            rejected_count += 1
            print(f"   ⚠️ Issue rejetée (hallucination) : {reason}")

    print(f"   ✅ {len(valid_issues)}/{len(issues)} issues validées")
    if rejected_count > 0:
        print(f"   🚫 {rejected_count} hallucination(s) filtrée(s)")

    return valid_issues