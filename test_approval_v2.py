import sys
sys.stdout.reconfigure(line_buffering=True)
from app.pr_approval import determine_review_action

print("=== Test REVUE-40 : Logique stricte axée sécurité ===\n")

# Test 1 : Faille de sécurité LOW severity → doit bloquer quand même
print("1️⃣ Test : Sécurité LOW severity")
issues1 = [{"severity": "low", "type": "security", "description": "Mineure faille"}]
result1 = determine_review_action(issues1)
print(f"   Résultat : {result1} (attendu: REQUEST_CHANGES)")

# Test 2 : Bug critique non-sécurité
print("\n2️⃣ Test : Bug critical non-security")
issues2 = [{"severity": "critical", "type": "bug", "description": "Crash garanti"}]
result2 = determine_review_action(issues2)
print(f"   Résultat : {result2} (attendu: REQUEST_CHANGES)")

# Test 3 : Seulement medium/low non-security
print("\n3️⃣ Test : Seulement medium/low non-security")
issues3 = [
    {"severity": "medium", "type": "logic", "description": "Logique douteuse"},
    {"severity": "low", "type": "bug", "description": "Mineur"}
]
result3 = determine_review_action(issues3)
print(f"   Résultat : {result3} (attendu: COMMENT)")

# Test 4 : Aucun problème
print("\n4️⃣ Test : Aucun problème")
result4 = determine_review_action([])
print(f"   Résultat : {result4} (attendu: APPROVE)")

# Test 5 : Mix - sécurité présente même avec d'autres types
print("\n5️⃣ Test : Mix avec sécurité présente")
issues5 = [
    {"severity": "low", "type": "logic", "description": "Mineur"},
    {"severity": "medium", "type": "security", "description": "Faille moyenne"}
]
result5 = determine_review_action(issues5)
print(f"   Résultat : {result5} (attendu: REQUEST_CHANGES)")