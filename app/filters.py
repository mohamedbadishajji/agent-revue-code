import os
from dotenv import load_dotenv

load_dotenv()

# Extensions de code à analyser
SUPPORTED_EXTENSIONS = [
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".java", ".c", ".cpp", ".cs", ".go",
    ".rb", ".php", ".swift", ".kt"
]

# Extensions à ignorer
IGNORED_EXTENSIONS = [
    ".md", ".lock", ".txt", ".png", ".jpg",
    ".jpeg", ".gif", ".svg", ".ico", ".pdf",
    ".zip", ".env", ".csv", ".xml", ".yaml",
    ".yml", ".toml", ".ini", ".cfg", ".log"
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
    ".min.css"
]

# Patterns de fichiers de test (REVUE-49 — Bug 2)
TEST_PATTERNS = [
    "test_",
    "_test.",
    ".test.",
    ".spec.",
    "/tests/",
    "/test/"
]


def is_test_file(file_path: str) -> bool:
    """Vérifie si un fichier est un fichier de test"""
    file_lower = file_path.lower()
    return any(pattern in file_lower for pattern in TEST_PATTERNS)


def is_auto_generated(file_path: str) -> bool:
    """Vérifie si un fichier est auto-généré"""
    file_lower = file_path.lower()
    return any(pattern in file_lower for pattern in IGNORED_PATTERNS)


def is_relevant(file_path: str, include_tests: bool = False) -> bool:
    """
    Vérifie si un fichier est pertinent pour l'analyse
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

    # Garder uniquement les extensions supportées
    if ext not in SUPPORTED_EXTENSIONS:
        return False

    return True


def filter_files(diff_files: list, include_tests: bool = False) -> list:
    """
    Filtre les fichiers non pertinents
    Critère US 2.1 : Les fichiers non pertinents sont filtrés
    """
    relevant_files = []
    ignored_files = []

    for file_data in diff_files:
        file_path = file_data["file_path"]
        if is_relevant(file_path, include_tests):
            relevant_files.append(file_data)
        else:
            ignored_files.append(file_path)

    # Résumé du filtrage
    print(f"✅ Fichiers pertinents : {len(relevant_files)}")
    if ignored_files:
        print(f"🚫 Fichiers ignorés : {len(ignored_files)}")
        for f in ignored_files:
            print(f"   - {f}")

    return relevant_files