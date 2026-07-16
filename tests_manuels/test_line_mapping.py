import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sys
sys.stdout.reconfigure(line_buffering=True)
from app.validator import validate_line_mapping, get_added_lines

print("=== Test REVUE-20/47 : Mapping de ligne ===\n")

# Patch de test
patch = """
@@ -1,4 +1,8 @@
 def hello():
+    password = "admin123"
+    api_key = "sk-123"
 
+def divide(a, b):
+    return a / b
+
 def existing():
     pass
"""

print("📋 Lignes ajoutées dans le patch :")
added_lines = get_added_lines(patch)
for line, position in added_lines.items():
    print(f"   Ligne {line} → position patch {position}")

# Issues avec différents cas de mapping
issues = [
    {
        "line": 2,
        "severity": "critical",
        "type": "security",
        "description": "Mot de passe hardcodé en clair dans le code source",
        "file_path": "app/utils.py"
    },
    {
        "line": 3,
        "severity": "critical",
        "type": "security",
        "description": "Clé API hardcodée en clair dans le code source",
        "file_path": "app/utils.py"
    },
    {
        "line": 5,
        "severity": "high",
        "type": "bug",
        "description": "Division par zéro possible si b vaut 0",
        "file_path": "app/utils.py"
    },
    {
        "line": 99,
        "severity": "medium",
        "type": "bug",
        "description": "Ligne inexistante dans le patch — hallucination",
        "file_path": "app/utils.py"
    }
]

print(f"\n📋 Issues à mapper : {len(issues)}")
validated = validate_line_mapping(issues, patch)

print(f"\n✅ Résultat du mapping :")
for issue in validated:
    status = "corrigée" if issue.get("line_mapping_corrected") else "valide"
    global_comment = "→ commentaire global" if issue.get("use_global_comment") else ""
    print(f"   Ligne {issue['line']} [{status}] position={issue.get('patch_position', 'N/A')} {global_comment}")
