from app.github_client import get_github_client
from dotenv import load_dotenv
import os

load_dotenv()

INSTALLATION_ID = int(os.getenv("GITHUB_INSTALLATION_ID"))

def get_pr_metadata(repo_name: str, pr_number: int):
    client = get_github_client(INSTALLATION_ID)
    repo = client.get_repo(repo_name)
    pr = repo.get_pull(pr_number)
    
    metadata = {
        "titre": pr.title,
        "auteur": pr.user.login,
        "numero": pr.number,
        "branche_source": pr.head.ref,
        "branche_cible": pr.base.ref,
        "fichiers_modifies": pr.changed_files,
        "additions": pr.additions,
        "deletions": pr.deletions,
        "statut": pr.state
    }
    
    return metadata