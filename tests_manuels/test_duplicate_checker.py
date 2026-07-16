import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sys
sys.stdout.reconfigure(line_buffering=True)
from app.duplicate_checker import filter_duplicate_issues, get_existing_comments

print("=== Test REVUE-23/50 : Commentaires dupliqués ===\n")

repo_name = input("Nom du repo : ")
pr_number = int(input("Numéro de la PR : "))

# Récupérer les commentaires existants
print("\n1️⃣ Récupération des commentaires existants...")
existing = get_existing_comments(repo_name, pr_number)
print(f"   Total commentaires agent trouvés : {len(existing)}")
for comment in existing:
    print(f"   - [{comment['type']}] fichier={comment['file_path']} ligne={comment['line']}")

# Simuler des issues — certaines déjà commentées
print("\n2️⃣ Test du filtre anti-doublons...")
fake_issues = [
    {
        "line": 4,
        "severity": "critical",
        "type": "security",
        "description": "Mot de passe hardcodé",
        "file_path": "buggy_code.py"
    },
    {
        "line": 9,
        "severity": "high",
        "type": "bug",
        "description": "Division par zéro possible",
        "file_path": "buggy_code.py"
    },
    {
        "line": 1,
        "severity": "low",
        "type": "style",
        "description": "Nouvelle issue pas encore commentée",
        "file_path": "buggy_code.py"
    }
]

new_issues = filter_duplicate_issues(fake_issues, repo_name, pr_number)

print(f"\n✅ Issues à poster : {len(new_issues)}")
for issue in new_issues:
    print(f"   - Ligne {issue['line']} [{issue['severity']}] : {issue['description']}")
