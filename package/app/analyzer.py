import json
from dotenv import load_dotenv
from app.diff_parser import extract_diff, parse_diff, chunk_diff
from app.filters import filter_files
from app.prompt import (
    build_summary_prompt,
    SYSTEM_PROMPT,
    build_language_specific_prompt,
)
from app.llm_client import invoke_llm
from app.validator import validate_issues
from app.config_loader import load_repo_config

load_dotenv()

MAX_TOTAL_LINES = 500
MAX_FILES_WHEN_LARGE = 10


def check_pr_size(diff_files: list) -> dict:
    """
    Calcule la taille totale de la PR et determine si une limitation est necessaire
    REVUE-48 : Timeout sur PRs > 500 lignes
    """
    total_lines = sum(len(f.get("added_lines", [])) for f in diff_files)

    is_large = total_lines > MAX_TOTAL_LINES

    return {
        "total_lines": total_lines,
        "is_large": is_large,
        "max_allowed": MAX_TOTAL_LINES,
    }


def limit_files_for_large_pr(
    parsed_files: list, max_files: int = MAX_FILES_WHEN_LARGE
) -> tuple:
    """
    Pour les grosses PRs, garde uniquement les fichiers avec le plus de changements
    Retourne (fichiers_analyses, fichiers_ignores_count)
    """
    sorted_files = sorted(
        parsed_files, key=lambda f: len(f.get("added_lines", [])), reverse=True
    )

    limited_files = sorted_files[:max_files]
    ignored_count = len(parsed_files) - len(limited_files)

    return limited_files, ignored_count


def clean_json_response(response: str) -> dict:
    """
    Nettoie et parse la réponse JSON du LLM
    Gère les backticks markdown
    """
    clean = response.strip()
    if clean.startswith("```"):
        clean = clean.split("```")[1]
        if clean.startswith("json"):
            clean = clean[4:]
    return json.loads(clean.strip())


def analyze_file(file_data: dict, pr_title: str, custom_instructions: str = "") -> dict:
    """
    Analyse un fichier avec le LLM
    REVUE-8 : Analyse par fichier avec gestion du contexte
    REVUE-45 : Utilise les instructions personnalisees du repo
    """
    file_path = file_data["file_path"]
    language = file_data["language"]
    patch = file_data["patch"]

    print(f"   Analyse de {file_path} ({language})...")

    prompt = build_language_specific_prompt(
        file_path=file_path,
        language=language,
        patch=patch,
        custom_instructions=custom_instructions,
    )

    try:
        response = invoke_llm(
            prompt=prompt, system_prompt=SYSTEM_PROMPT, max_tokens=2000
        )

        result = clean_json_response(response)

        for issue in result.get("issues", []):
            issue["file_path"] = file_path
            issue["language"] = language

        validated_issues = validate_issues(result.get("issues", []), patch)
        result["issues"] = validated_issues

        print(f"   {len(validated_issues)} probleme(s) valide(s) apres validation")
        return result

    except Exception as e:
        print(f"   Erreur analyse {file_path} : {str(e)}")
        return {"issues": [], "summary": f"Erreur lors de l'analyse : {str(e)}"}


def analyze_pr(
    repo_name: str, pr_number: int, pr_title: str = "", include_tests: bool = False
) -> dict:
    """
    Analyse complète d'une PR
    Orchestre toutes les étapes de l'analyse
    REVUE-44 : Utilise la configuration personnalisée du repo
    REVUE-48 : Gere les PRs volumineuses
    """
    from app.scoring import calculate_severity_score, generate_score_report

    print(f"\n Debut de l'analyse de la PR #{pr_number}\n")

    # Étape 0 : Charger la configuration personnalisée du repo (REVUE-44)
    print("0 Chargement de la configuration du repository...")
    config = load_repo_config(repo_name)

    # Étape 1 : Extraire le diff
    print("1 Extraction du diff...")
    diff_files = extract_diff(repo_name, pr_number)

    # Étape 2 : Parser le diff
    print("2 Parsing du diff...")
    parsed_files = parse_diff(diff_files)

    # Étape 3 : Filtrer les fichiers (avec config personnalisée)
    print("3 Filtrage des fichiers...")
    use_include_tests = config["include_tests"] or include_tests
    filtered_files = filter_files(
        parsed_files,
        include_tests=use_include_tests,
        languages_enabled=config.get("languages_enabled"),
        max_file_size_kb=config.get("max_file_size_kb"),
    )
    print(f"   ✅ {len(filtered_files)} fichier(s) après filtrage config")

    if not filtered_files:
        print("Aucun fichier pertinent a analyser")
        return {
            "pr_number": pr_number,
            "repo_name": repo_name,
            "total_issues": 0,
            "issues": [],
            "summary": "Aucun fichier de code a analyser.",
            "scoring": calculate_severity_score([]),
            "score_report": generate_score_report([], repo_name, pr_number),
            "pr_size_warning": None,
            "file_line_counts": {},
        }

    # Étape 3.5 : Vérifier la taille de la PR (REVUE-48)
    print("3.5 Verification de la taille de la PR...")
    size_info = check_pr_size(filtered_files)
    pr_size_warning = None

    if size_info["is_large"]:
        print(
            f"   ⚠️ PR volumineuse : {size_info['total_lines']} lignes (max recommande : {size_info['max_allowed']})"
        )
        filtered_files, ignored_count = limit_files_for_large_pr(filtered_files)
        pr_size_warning = (
            f"⚠️ **PR volumineuse détectée** ({size_info['total_lines']} lignes modifiées). "
            f"Pour des raisons de performance, seuls les {len(filtered_files)} fichiers "
            f"les plus impactés ont été analysés en priorité. "
            f"{ignored_count} fichier(s) supplémentaire(s) n'ont pas été analysés dans cette passe."
        )
        print(f"   ✅ Analyse limitee a {len(filtered_files)} fichier(s) prioritaires")
    else:
        print(f"   ✅ Taille de PR normale : {size_info['total_lines']} lignes")

    # Étape 4 : Chunking si nécessaire
    print("4 Chunking du diff...")
    chunks = chunk_diff(filtered_files)

    # Étape 5 : Analyser chaque fichier
    print(f"\n5 Analyse de {len(filtered_files)} fichier(s) avec le LLM...\n")
    all_issues = []
    all_summaries = []

    for chunk in chunks:
        for file_data in chunk:
            result = analyze_file(
                file_data, pr_title, config.get("custom_instructions", "")
            )
            all_issues.extend(result.get("issues", []))
            if result.get("summary"):
                all_summaries.append(result["summary"])

    # Étape 6 : Générer le résumé global
    print(f"\n6 Generation du resume global...")
    if all_issues:
        summary_prompt = build_summary_prompt(all_issues, pr_title)
        global_summary = invoke_llm(prompt=summary_prompt, max_tokens=500)
    else:
        global_summary = "Aucun probleme detecte dans cette PR."

    # Étape 7 : Calcul du score de sévérité (REVUE-36)
    print(f"\n7 Calcul du score de severite...")
    scoring = calculate_severity_score(all_issues)
    score_report = generate_score_report(all_issues, repo_name, pr_number)

    # Capturer le nombre exact de lignes ajoutées par fichier (pour temps gagne precis)
    file_line_counts = {
        f["file_path"]: len(f.get("added_lines", [])) for f in filtered_files
    }

    print(f"\nAnalyse terminee — {len(all_issues)} probleme(s) au total")
    print(
        f"Score de risque : {scoring['score']}/100 — {scoring['risk_level']['emoji']} {scoring['risk_level']['level']}"
    )

    # Ajouter l'avertissement de taille au résumé si applicable (REVUE-48)
    final_summary = global_summary
    if pr_size_warning:
        final_summary = f"{pr_size_warning}\n\n---\n\n{global_summary}"

    return {
        "pr_number": pr_number,
        "repo_name": repo_name,
        "total_issues": len(all_issues),
        "issues": all_issues,
        "summary": final_summary,
        "scoring": scoring,
        "score_report": score_report,
        "pr_size_warning": pr_size_warning,
        "file_line_counts": file_line_counts,
    }
