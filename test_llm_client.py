from app.llm_client import invoke_llm

print("=== Test REVUE-32 : Connexion AWS Bedrock ===\n")

# Test simple
print("1️⃣ Test de connexion...")
response = invoke_llm(
    prompt="Réponds uniquement par 'Connexion AWS Bedrock réussie ✅'",
    system_prompt="Tu es un assistant de test. Réponds exactement ce qu'on te demande.",
    max_tokens=50
)
print(f"Réponse : {response}")

# Test avec du code Python
print("\n2️⃣ Test analyse de code simple...")
code = """
def division(a, b):
    return a / b
"""
response2 = invoke_llm(
    prompt=f"Analyse ce code Python et dis-moi s'il y a un bug en une phrase :\n{code}",
    system_prompt="Tu es un expert en revue de code. Sois concis.",
    max_tokens=100
)
print(f"Analyse : {response2}")