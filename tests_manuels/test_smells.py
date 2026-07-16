import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sys
sys.stdout.reconfigure(line_buffering=True)
import json
from app.prompt import build_code_smells_prompt, SYSTEM_PROMPT_SMELLS
from app.llm_client import invoke_llm

print("=== Test REVUE-9 : Détection Code Smells ===\n")

# Code avec plusieurs code smells
patch = """
@@ -1,30 +1,35 @@
+def f(a, b, c, d, e):
+    x = a * b
+    y = c * d
+    z = x + y + e
+    if z > 100:
+        print("big")
+    elif z > 50:
+        print("medium")
+    else:
+        print("small")
+    result = z * 2
+    final = result + 10
+    return final
+
+def calc(p, q):
+    return p * q * 3.14159
+
+def calculate_area(p, q):
+    return p * q * 3.14159
"""

print("1️⃣ Construction du prompt...")
prompt = build_code_smells_prompt(
    file_path="app/utils.py",
    language="python",
    patch=patch
)
print("✅ Prompt construit")

print("\n2️⃣ Envoi au LLM AWS Bedrock...")
response = invoke_llm(
    prompt=prompt,
    system_prompt=SYSTEM_PROMPT_SMELLS,
    max_tokens=1000
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
    print(f"\n📊 Score qualité : {result['quality_score']}/10")
    print(f"📝 Résumé : {result['summary']}")
    print(f"🔍 Code smells détectés : {len(result['smells'])}")

    for smell in result['smells']:
        print(f"\n  Ligne {smell['line']} [{smell['type']}]")
        print(f"  Description : {smell['description']}")
        print(f"  Suggestion  : {smell['suggestion']}")

except json.JSONDecodeError as e:
    print(f"❌ Erreur JSON : {e}")
    print(f"Réponse brute : {response}")
