import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sys
sys.stdout.reconfigure(line_buffering=True)
from app.main import process_pull_request_with_retry

print("=== Test REVUE-50 : Mecanisme de retry ===\n")

# Simuler une fonction qui echoue 2 fois puis reussit
attempt_counter = {"count": 0}

def fake_process(repo_name, pr_number, pr_title):
    attempt_counter["count"] += 1
    print(f"   Tentative interne #{attempt_counter['count']}")
    if attempt_counter["count"] < 3:
        raise Exception("Erreur simulee (ex: AWS Bedrock timeout)")
    print("   Traitement reussi !")

# Remplacer temporairement process_pull_request par notre version simulee
import app.main
app.main.process_pull_request = fake_process

print("Lancement du traitement avec retry...\n")
process_pull_request_with_retry("test/repo", 999, "Test PR")

print(f"\nNombre total de tentatives : {attempt_counter['count']}")
