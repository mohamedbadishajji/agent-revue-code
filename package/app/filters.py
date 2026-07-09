import os
from dotenv import load_dotenv

load_dotenv()

# Extensions de code à analyser
SUPPORTED_EXTENSIONS = [
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".java",
    ".c",
    ".cpp",
    ".cs",
    ".go",
    ".rb",
    ".php",
    ".swift",
    ".kt",
]

# Extensions à ignorer
IGNORED_EXTENSIONS = [
    ".md",
    ".lock",
    ".txt",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".pdf",
    ".zip",
    ".env",
    ".csv",
    ".xml",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".log",
]

# Patterns de fichiers auto-générés à ignorer
IGNORED_PATTERNS = [
    "package-lock.json",
    "yarn.lock",
    "poetry.lock",
    "Pipfile.lock",
    "composer.lock",
    "__pycache__",
    ".pyc",
    "node_modules",
    "dist/",
    "build/",
    ".min.js",
    ".min.css",
]

# Patterns de fichiers de test (REVUE-49 — Bug 2)
TEST_PATTERNS = ["test_", "_test.", ".test.", ".spec.", "/tests/", "/test/"]

# Correspondance extension -> langage (REVUE-45)
EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".php": "php",
    ".rb": "ruby",
    ".cs": "csharp",
    ".swift": "swift",
    ".kt": "kotlin",
    ".c": "c",
    ".cpp": "cpp",
    ".rs": "rust",
    ".dart": "dart",
    ".scala": "scala",
    ".r": "r",
    ".sh": "bash",
    ".pl": "perl",
    ".lua": "lua",
    ".sql": "sql",
    ".vue": "javascript",
    ".mjs": "javascript",
}


def is_test_file(file_path: str) -> bool:
    """Vérifie si un fichier est un fichier de test"""
    file_lower = file_path.lower()
    return any(pattern in file_lower for pattern in TEST_PATTERNS)


def is_auto_generated(file_path: str) -> bool:
    """Vérifie si un fichier est auto-généré"""
    file_lower = file_path.lower()
    return any(pattern in file_lower for pattern in IGNORED_PATTERNS)


def exceeds_max_size(file_data: dict, max_file_size_kb: int = None) -> bool:
    """
    Vérifie si la taille du patch dépasse la limite configurée
    REVUE-45 : Respecte max_file_size_kb de la config du repo
    """
    if not max_file_size_kb:
        return False

    patch = file_data.get("patch", "")
    size_kb = len(patch.encode("utf-8")) / 1024

    return size_kb > max_file_size_kb


def is_relevant(
    file_path: str, include_tests: bool = False, languages_enabled: list = None
) -> bool:
    """
    Vérifie si un fichier est pertinent pour l'analyse
    REVUE-45 : Respecte la liste languages_enabled de la config du repo
    Retourne True si le fichier doit être analysé
    """
    # Vérifier l'extension
    ext = os.path.splitext(file_path)[1].lower()

    # Ignorer les extensions non supportées
    if ext in IGNORED_EXTENSIONS:
        return False

    # Ignorer les fichiers auto-générés
    if is_auto_generated(file_path):
        return False

    # Ignorer les fichiers de test si demandé (REVUE-49)
    if not include_tests and is_test_file(file_path):
        return False

    # REVUE-35 (extension) : Accepter TOUS les langages, pas seulement la liste initiale
    # Les langages non specifiquement configures utilisent des regles generiques
    file_language = EXTENSION_TO_LANGUAGE.get(ext, "unknown")

    # Filtrer selon la config languages_enabled du repo UNIQUEMENT si elle est definie
    # ET que le fichier a un langage reconnu (sinon on le laisse passer par defaut)
    if languages_enabled and file_language != "unknown":
        if file_language not in languages_enabled:
            return False

    return True


def filter_files(
    diff_files: list,
    include_tests: bool = False,
    languages_enabled: list = None,
    max_file_size_kb: int = None,
) -> list:
    """
    Filtre les fichiers non pertinents
    Critère US 2.1 : Les fichiers non pertinents sont filtrés
    REVUE-45 : Filtre selon les langages autorisés et la taille max configurée
    """
    relevant_files = []
    ignored_files = []

    for file_data in diff_files:
        file_path = file_data["file_path"]

        if not is_relevant(file_path, include_tests, languages_enabled):
            ignored_files.append(f"{file_path} (non pertinent)")
            continue

        if exceeds_max_size(file_data, max_file_size_kb):
            ignored_files.append(f"{file_path} (taille > {max_file_size_kb}KB)")
            continue

        relevant_files.append(file_data)

    # Résumé du filtrage
    print(f"✅ Fichiers pertinents : {len(relevant_files)}")
    if ignored_files:
        print(f"🚫 Fichiers ignorés : {len(ignored_files)}")
        for f in ignored_files:
            print(f"   - {f}")

    return relevant_files
