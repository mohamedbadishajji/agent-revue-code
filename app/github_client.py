from github import GithubIntegration, Github
from dotenv import load_dotenv
import os

load_dotenv()

APP_ID = os.getenv("GITHUB_APP_ID")
PRIVATE_KEY_PATH = os.getenv("GITHUB_PRIVATE_KEY_PATH")
PRIVATE_KEY_CONTENT = os.getenv("GITHUB_PRIVATE_KEY")


def reconstruct_pem_format(flat_key: str) -> str:
    """
    Reconstruit le format PEM multi-lignes a partir d'une cle aplatie sur une seule ligne
    """
    flat_key = flat_key.strip()

    header = "-----BEGIN RSA PRIVATE KEY-----"
    footer = "-----END RSA PRIVATE KEY-----"

    if header in flat_key and footer in flat_key:
        body = flat_key.replace(header, "").replace(footer, "").strip()
        body = body.replace(" ", "")
        lines = [body[i:i+64] for i in range(0, len(body), 64)]
        return header + "\n" + "\n".join(lines) + "\n" + footer + "\n"

    return flat_key


def load_private_key() -> str:
    """
    Charge la clé privée GitHub depuis un fichier (local) ou directement
    depuis une variable d'environnement (production - Azure/AWS Lambda)
    Gère le cas où les retours a la ligne sont aplatis par Azure CLI
    """
    # Priorité 1 : variable d'environnement avec le contenu direct (production)
    if PRIVATE_KEY_CONTENT:
        key = PRIVATE_KEY_CONTENT
        # Restaurer les vrais retours a la ligne si necessaire
        if "\\n" in key and "\n" not in key:
            key = key.replace("\\n", "\n")
        # Si toujours sur une seule ligne, reconstruire le format PEM
        if key.count("\n") < 2:
            key = reconstruct_pem_format(key)
        return key

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