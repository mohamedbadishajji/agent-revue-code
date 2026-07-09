from dotenv import load_dotenv
import os

load_dotenv()

APP_ID = os.getenv("GITHUB_APP_ID")
INSTALLATION_ID = int(os.getenv("GITHUB_INSTALLATION_ID"))
MAX_TOKENS = 128000  # Limite de tokens du LLM (Bug 1)

# Extensions de fichiers à analyser
SUPPORTED_EXTENSIONS = [".py", ".js", ".ts", ".jsx", ".tsx"]

# Extensions à ignorer (Bug 1 — filtrage préventif)
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
]


def get_language(file_path: str) -> str:
    """Détecte le langage de programmation selon l'extension"""
    ext = os.path.splitext(file_path)[1].lower()
    languages = {
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
        ".cc": "cpp",
        ".h": "c",
        ".hpp": "cpp",
    }
    return languages.get(ext, "unknown")


def estimate_tokens(text: str) -> int:
    """Estime le nombre de tokens (1 token ≈ 4 caractères)"""
    return len(text) // 4


def extract_diff(repo_name: str, pr_number: int) -> list:
    """
    Récupère le diff de tous les fichiers modifiés dans la PR
    Critère 1 : L'API GitHub est appelée pour récupérer le patch/diff
    """
    from app.github_client import get_github_client

    client = get_github_client(INSTALLATION_ID)
    repo = client.get_repo(repo_name)
    pr = repo.get_pull(pr_number)

    files = pr.get_files()
    diff_files = []

    for file in files:
        # Ignorer les fichiers sans patch (fichiers binaires, etc.)
        if not file.patch:
            continue

        diff_files.append(
            {
                "file_path": file.filename,
                "language": get_language(file.filename),
                "patch": file.patch,
                "additions": file.additions,
                "deletions": file.deletions,
                "status": file.status,  # added, modified, removed
            }
        )

    print(f"✅ {len(diff_files)} fichiers avec diff récupérés")
    return diff_files


def parse_diff(diff_files: list) -> list:
    """
    Parse le diff brut pour extraire les lignes ajoutées avec leurs numéros
    """
    parsed_files = []

    for file_data in diff_files:
        patch = file_data["patch"]
        added_lines = []
        current_line = 0
        patch_position = 0

        for line in patch.splitlines():
            patch_position += 1

            # Extraire le numéro de ligne depuis l'en-tête du hunk
            if line.startswith("@@"):
                import re

                match = re.search(r"\+(\d+)", line)
                if match:
                    current_line = int(match.group(1)) - 1

            elif line.startswith("+") and not line.startswith("+++"):
                current_line += 1
                added_lines.append(
                    {
                        "line_number": current_line,
                        "content": line[1:],  # Enlever le +
                        "patch_position": patch_position,  # Pour Bug 3
                    }
                )

            elif not line.startswith("-"):
                current_line += 1

        parsed_files.append(
            {
                "file_path": file_data["file_path"],
                "language": file_data["language"],
                "patch": patch,
                "added_lines": added_lines,
                "token_count": estimate_tokens(patch),
                "status": file_data["status"],
            }
        )

    return parsed_files


def chunk_diff(parsed_files: list, max_tokens: int = MAX_TOKENS) -> list:
    """
    Découpe le diff en chunks pour respecter les limites de tokens
    Bug 1 du cahier des charges : Token Limit Exceeded
    """
    chunks = []
    current_chunk = []
    current_tokens = 0

    for file_data in parsed_files:
        file_tokens = file_data["token_count"]

        # Si un seul fichier dépasse la limite → on l'ignore avec avertissement
        if file_tokens > max_tokens:
            print(
                f"⚠️ Fichier {file_data['file_path']} trop grand ({file_tokens} tokens) — ignoré"
            )
            continue

        # Si ajouter ce fichier dépasse la limite → nouveau chunk
        if current_tokens + file_tokens > max_tokens and current_chunk:
            chunks.append(current_chunk)
            current_chunk = []
            current_tokens = 0

        current_chunk.append(file_data)
        current_tokens += file_tokens

    # Ajouter le dernier chunk
    if current_chunk:
        chunks.append(current_chunk)

    print(f"✅ Diff découpé en {len(chunks)} chunk(s)")
    return chunks
