import sys
sys.stdout.reconfigure(line_buffering=True)
from app.scoring import calculate_severity_score, generate_score_report

print("=== Test REVUE-36 : Système de scoring de sévérité ===\n")

# Test 1 : Issues de la PR #4 (buggy_code.py)
print("1️⃣ Test avec issues critiques (PR #4)...")
issues_pr4 = [
    {"line": 4, "severity": "critical", "type": "security", "owasp": "A02:2021", "description": "Mot de passe hardcodé"},
    {"line": 5, "severity": "critical", "type": "security", "owasp": "A02:2021", "description": "Clé API hardcodée"},
    {"line": 12, "severity": "critical", "type": "security", "owasp": "A03:2021", "description": "SQL Injection"},
    {"line": 17, "severity": "critical", "type": "security", "owasp": "A03:2021", "description": "Command Injection"},
    {"line": 21, "severity": "critical", "type": "security", "owasp": "A08:2021", "description": "Insecure Deserialization"},
    {"line": 9, "severity": "high", "type": "bug", "description": "Division par zéro"},
]

result = calculate_severity_score(issues_pr4)
print(f"   Score : {result['score']}/100")
print(f"   Niveau : {result['risk_level']['emoji']} {result['risk_level']['level']}")
print(f"   Points déduits : {result['total_points']}")
print(f"   Description : {result['risk_level']['description']}")

# Test 2 : Issues de la PR #5 (buggy_code.js)
print("\n2️⃣ Test avec issues JavaScript (PR #5)...")
issues_pr5 = [
    {"line": 9, "severity": "critical", "type": "security", "description": "Mot de passe hardcodé"},
    {"line": 12, "severity": "critical", "type": "security", "description": "console.log mot de passe"},
    {"line": 22, "severity": "high", "type": "security", "description": "XSS via document.write"},
    {"line": 16, "severity": "high", "type": "bug", "description": "Promise non gérée"},
    {"line": 3, "severity": "low", "type": "bug", "description": "== au lieu de ==="},
]

result2 = calculate_severity_score(issues_pr5)
print(f"   Score : {result2['score']}/100")
print(f"   Niveau : {result2['risk_level']['emoji']} {result2['risk_level']['level']}")
print(f"   Points déduits : {result2['total_points']}")

# Test 3 : Code propre
print("\n3️⃣ Test avec code propre (aucune issue)...")
result3 = calculate_severity_score([])
print(f"   Score : {result3['score']}/100")
print(f"   Niveau : {result3['risk_level']['emoji']} {result3['risk_level']['level']}")

# Test 4 : Rapport complet
print("\n4️⃣ Rapport de scoring complet (PR #4)...")
report = generate_score_report(issues_pr4, "mohamedbadishajji/test_agent_revue", 4)
print(report)