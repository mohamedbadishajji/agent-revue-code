import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sys
sys.stdout.reconfigure(line_buffering=True)
from app.validator import validate_issues, get_lines_in_patch

print("=== Test REVUE-21 : Validation post-LLM ===\n")

# Patch de test
patch = """
@@ -1,4 +1,6 @@
+def divide(a, b):
+    return a / b
+
+password = "admin123"
"""

# Issues simulées — mélange de vraies et d'hallucinations
fake_issues = [
    {
        "line": 1,
        "severity": "high",
        "type": "bug",
        "description": "Division par zéro possible si b vaut 0 — vérification manquante",
        "file_path": "app/utils.py",
        "language": "python"
    },
    {
        "line": 4,
        "severity": "critical",
        "type": "security",
        "description": "Mot de passe hardcodé en clair dans le code source",
        "file_path": "app/utils.py",
        "language": "python"
    },
    {
        "line": 99,
        "severity": "high",
        "type": "bug",
        "description": "La fonction multiply() pourrait causer des problèmes",
        "file_path": "app/utils.py",
        "language": "python"
    },
    {
        "line": 50,
        "severity": "medium",
        "type": "bug",
        "description": "Erreur possible",
        "file_path": "app/utils.py",
        "language": "python"
    }
]

print("📋 Issues soumises au validateur :")
for issue in fake_issues:
    print(f"   - Ligne {issue['line']} [{issue['severity']}] : {issue['description'][:50]}")

print("\n🔍 Lignes valides dans le patch :")
valid_lines = get_lines_in_patch(patch)
print(f"   {valid_lines}")

print()
valid_issues = validate_issues(fake_issues, patch)

print(f"\n✅ Issues valides retenues :")
for issue in valid_issues:
    print(f"   - Ligne {issue['line']} [{issue['severity']}] : {issue['description'][:50]}")
