import sys
sys.stdout.reconfigure(line_buffering=True)
from app.rate_limiter import retry_with_backoff, check_rate_limit, batch_post_comments
from app.github_client import get_github_client
import os
from dotenv import load_dotenv

load_dotenv()

INSTALLATION_ID = int(os.getenv("GITHUB_INSTALLATION_ID"))

print("=== Test REVUE-22 : Rate Limiting GitHub API ===\n")

# Test 1 : Vérifier le rate limit actuel
print("1️⃣ Vérification du quota GitHub API...")
client = get_github_client(INSTALLATION_ID)
rate_info = check_rate_limit(client)
print(f"   Requêtes restantes : {rate_info['remaining']}/{rate_info['limit']}")

# Test 2 : Décorateur retry_with_backoff
print("\n2️⃣ Test du décorateur backoff...")

attempt_count = 0

@retry_with_backoff(max_retries=3, initial_wait=1)
def fake_api_call():
    global attempt_count
    attempt_count += 1
    if attempt_count < 3:
        raise Exception("rate limit exceeded 403")
    return "Succès après 3 tentatives"

try:
    result = fake_api_call()
    print(f"   ✅ {result}")
except Exception as e:
    print(f"   ❌ {str(e)}")

# Test 3 : Batch posting
print("\n3️⃣ Test du posting par lots...")

posted_count = 0

def fake_post(**kwargs):
    global posted_count
    posted_count += 1
    print(f"   📤 Commentaire {posted_count} posté")
    return True

fake_comments = [{"id": i} for i in range(8)]

total = batch_post_comments(
    post_func=fake_post,
    comments=fake_comments,
    batch_size=3,
    delay=0.2
)

print(f"\n✅ Total posté : {total}/8")