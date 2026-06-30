from github import GithubIntegration, Github
from dotenv import load_dotenv
import os

load_dotenv()

APP_ID = os.getenv("GITHUB_APP_ID")
PRIVATE_KEY_PATH = os.getenv("GITHUB_PRIVATE_KEY_PATH")
PRIVATE_KEY_CONTENT = os.getenv("GITHUB_PRIVATE_KEY")


def load_private_key() -> str:
    """
    Charge la clé privée GitHub depuis un fichier (local) ou directement
    depuis une variable d'environnement (production - Azure/AWS Lambda)
    """
    # Priorité 1 : variable d'environnement avec le contenu direct (production)
    if PRIVATE_KEY_CONTENT:
        return PRIVATE_KEY_CONTENT

    # Priorité 2 : fichier .pem local (développement)
    if PRIVATE_KEY_PATH and os.path.exists(PRIVATE_KEY_PATH):
        with open(PRIVATE_KEY_PATH, "r") as f:
            return f.read()

    raise ValueError(
        "Clé privée GitHub introuvable. "
        "Configurez GITHUB_PRIVATE_KEY (contenu direct) "
        "ou GITHUB_PRIVATE_KEY_PATH (chemin vers le fichier .pem)"
    )


PRIVATE_KEY = load_private_key()


def get_github_client(installation_id: int):
    integration = GithubIntegration(APP_ID, PRIVATE_KEY)
    token = integration.get_access_token(installation_id).token
    return Github(token)