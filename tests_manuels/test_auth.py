import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from github import GithubIntegration
from dotenv import load_dotenv
import os

load_dotenv()

APP_ID = os.getenv("GITHUB_APP_ID")
PRIVATE_KEY_PATH = os.getenv("GITHUB_PRIVATE_KEY_PATH")

print(f"APP_ID : {APP_ID}")
print(f"PRIVATE_KEY_PATH : {PRIVATE_KEY_PATH}")

with open(PRIVATE_KEY_PATH, "r") as f:
    PRIVATE_KEY = f.read()

print("Clé privée chargée ✅")

integration = GithubIntegration(APP_ID, PRIVATE_KEY)
installations = integration.get_installations()
liste = list(installations)
print(f"Nombre d'installations : {len(liste)}")

for installation in liste:
    print(f"✅ Installation ID : {installation.id}")
    print(f"✅ Compte : {installation.account.login}")
