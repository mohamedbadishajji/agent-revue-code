import sys
sys.stdout.reconfigure(line_buffering=True)
import json
from app.prompt import build_code_review_prompt, SYSTEM_PROMPT
from app.llm_client import invoke_llm

print("=== Test REVUE-7/34 : Prompt Engineering ===\n")

# Test avec un code qui contient un bug évident
patch = """
@@ -1,4 +1,6 @@
+def divide(a, b):
+    return a / b
+
+password = "admin123"
+SECRET_KEY = "hardcoded_secret_key_123"
"""

print("1️⃣ Construction du prompt...")
prompt = build_code_review_prompt(
    file_path="app/utils.py",
    language="python",
    patch=patch
)
print("✅ Prompt construit")

print("\n2️⃣ Envoi au LLM AWS Bedrock...")
response = invoke_llm(
    prompt=prompt,
    system_prompt=SYSTEM_PROMPT,
    max_tokens=1000
)
print("✅ Réponse reçue")

print("\n3️⃣ Parsing de la réponse JSON...")
try:
    # Nettoyer les backticks markdown
    clean_response = response.strip()
    if clean_response.startswith("```"):
        clean_response = clean_response.split("```")[1]
        if clean_response.startswith("json"):
            clean_response = clean_response[4:]
    clean_response = clean_response.strip()

    result = json.loads(clean_response)
    print(f"✅ JSON valide")
    print(f"\n📊 Résumé : {result['summary']}")
    print(f"🐛 Problèmes détectés : {len(result['issues'])}")
    for issue in result['issues']:
        print(f"\n   Ligne {issue['line']} [{issue['severity']}] — {issue['type']}")
        print(f"   Description : {issue['description']}")
        print(f"   Suggestion  : {issue['suggestion']}")
except json.JSONDecodeError as e:
    print(f"❌ Erreur JSON : {e}")
    print(f"Réponse brute : {response}")