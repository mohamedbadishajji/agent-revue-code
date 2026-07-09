import os
import yaml
from dotenv import load_dotenv
from app.github_client import get_github_client

load_dotenv()

INSTALLATION_ID = int(os.getenv("GITHUB_INSTALLATION_ID"))

CONFIG_FILENAME = ".revue-config.yml"

DEFAULT_CONFIG = {
    "severity_threshold": "high",
    "include_tests": False,
    "ignored_paths": [],
    "max_file_size_kb": 1000,
    "custom_instructions": "",
    "languages_enabled": []
}


def get_default_config() -> dict:
    """
    Retourne la configuration par défaut
    REVUE-44 : Configuration par défaut si aucun fichier trouvé
    """
    return DEFAULT_CONFIG.copy()


def validate_config(config: dict) -> dict:
    """
    Valide et complète la configuration avec les valeurs par défaut manquantes
    """
    validated = get_default_config()

    if not isinstance(config, dict):
        print("   ⚠️ Configuration invalide — utilisation des valeurs par défaut")
        return validated

    # Fusionner avec les valeurs par défaut pour les clés manquantes
    for key in DEFAULT_CONFIG:
        if key in config:
            validated[key] = config[key]

    # Validation du severity_threshold
    valid_thresholds = ["critical", "high", "medium", "low"]
    if validated["severity_threshold"] not in valid_thresholds:
        print(f"   ⚠️ severity_threshold invalide — utilisation de 'high' par défaut")
        validated["severity_threshold"] = "high"

    return validated


def load_repo_config(repo_name: str) -> dict:
    """
    Charge la configuration personnalisée d'un repository
    REVUE-44 : Créer un fichier de configuration par repository
    """
    try:
        client = get_github_client(INSTALLATION_ID)
        repo = client.get_repo(repo_name)

        try:
            file_content = repo.get_contents(CONFIG_FILENAME)
            config_text = file_content.decoded_content.decode("utf-8")

            config = yaml.safe_load(config_text)
            validated_config = validate_config(config)

            print(f"   ✅ Configuration personnalisée chargée depuis {CONFIG_FILENAME}")
            return validated_config

        except Exception:
            print(
                f"   ℹ️ Aucun fichier {CONFIG_FILENAME} trouvé — utilisation de la configuration par défaut"
            )
            return get_default_config()

    except Exception as e:
        print(f"   ⚠️ Erreur chargement configuration : {str(e)}")
        return get_default_config()


def is_path_ignored(file_path: str, ignored_paths: list) -> bool:
    """
    Vérifie si un fichier doit être ignoré selon la configuration
    """
    for ignored in ignored_paths:
        if file_path.startswith(ignored) or ignored in file_path:
            return True
    return False
