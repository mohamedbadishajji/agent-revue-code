import sys
sys.stdout.reconfigure(line_buffering=True)
import json
from app.prompt import build_security_prompt, SYSTEM_PROMPT_SECURITY
from app.llm_client import invoke_llm

print("=== Test REVUE-10/37 : Détection Vulnérabilités Sécurité ===\n")

# Code avec plusieurs vulnérabilités
patch = """
@@ -1,30 +1,35 @@
+import os
+import pickle
+import hashlib
+import random
+import yaml
+
+# Credentials hardcodes
+DB_PASSWORD = "super_secret_123"
+API_KEY = "sk-1234567890abcdef"
+
+# SQL Injection
+def get_user(username):
+    query = "SELECT * FROM users WHERE username = '" + username + "'"
+    return query
+
+# Command Injection
+def run_command(user_input):
+    os.system("ls " + user_input)
+
+# Deserialisation non securisee
+def load_data(data):
+    return pickle.loads(data)
+
+# Cryptographie faible
+def hash_password(password):
+    return hashlib.md5(password.encode()).hexdigest()
+
+# Path Traversal
+def read_file(filename):
+    with open("/var/www/" + filename, "r") as f:
+        return f.read()
+
+# Insecure Random
+def generate_token():
+    return random.randint(0, 999999)
+
+# YAML non securise
+def parse_config(data):
+    return yaml.load(data)
"""

print("1️⃣ Construction du prompt...")
prompt = build_security_prompt(
    file_path="app/security_test.py",
    language="python",
    patch=patch
)
print("✅ Prompt construit")

print("\n2️⃣ Envoi au LLM AWS Bedrock...")
response = invoke_llm(
    prompt=prompt,
    system_prompt=SYSTEM_PROMPT_SECURITY,
    max_tokens=2000
)
print("✅ Réponse reçue")

print("\n3️⃣ Parsing de la réponse JSON...")
try:
    clean = response.strip()
    if clean.startswith("```"):
        clean = clean.split("```")[1]
        if clean.startswith("json"):
            clean = clean[4:]
    result = json.loads(clean.strip())

    print(f"✅ JSON valide")
    print(f"\n🔴 Score de risque : {result['risk_score']}/10")
    print(f"📝 Résumé : {result['summary']}")
    print(f"🔍 Vulnérabilités détectées : {len(result['vulnerabilities'])}")

    for vuln in result['vulnerabilities']:
        print(f"\n  [{vuln['severity']}] Ligne {vuln['line']} — {vuln['type']}")
        print(f"  OWASP : {vuln['owasp']}")
        print(f"  Description : {vuln['description']}")
        print(f"  Impact : {vuln['impact']}")
        print(f"  Suggestion : {vuln['suggestion']}")

except json.JSONDecodeError as e:
    print(f"❌ Erreur JSON : {e}")
    print(f"Réponse brute : {response}")