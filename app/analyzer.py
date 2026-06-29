import json
import os
from dotenv import load_dotenv
from app.diff_parser import extract_diff, parse_diff, chunk_diff
from app.filters import filter_files
from app.prompt import build_code_review_prompt, build_summary_prompt, SYSTEM_PROMPT, build_language_specific_prompt
from app.llm_client import invoke_llm
from app.validator import validate_issues
from app.scoring import calculate_severity_score, generate_score_report

load_dotenv()


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


def analyze_file(file_data: dict, pr_title: str) -> dict:
    """
    Analyse un fichier avec le LLM
    REVUE-8 : Analyse par fichier avec gestion du contexte
    """
    file_path = file_data["file_path"]
    language = file_data["language"]
    patch = file_data["patch"]

    print(f"   Analyse de {file_path} ({language})...")

    prompt = build_language_specific_prompt(
    file_path=file_path,
    language=language,
    patch=patch
)

    try:
        response = invoke_llm(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            max_tokens=2000
        )

        result = clean_json_response(response)

        # Ajouter le contexte à chaque issue
        for issue in result.get("issues", []):
            issue["file_path"] = file_path
            issue["language"] = language

        # Validation post-LLM — filtrer les hallucinations (REVUE-21)
        validated_issues = validate_issues(result.get("issues", []), patch)
        result["issues"] = validated_issues

        print(f"   {len(validated_issues)} probleme(s) valide(s) apres validation")
        return result

    except Exception as e:
        print(f"   Erreur analyse {file_path} : {str(e)}")
        return {"issues": [], "summary": f"Erreur lors de l'analyse : {str(e)}"}


def analyze_pr(repo_name: str, pr_number: int, pr_title: str = "", include_tests: bool = False) -> dict:
    """
    Analyse complète d'une PR
    Orchestre toutes les étapes de l'analyse
    """
    print(f"\n Debut de l'analyse de la PR #{pr_number}\n")

    # Étape 1 : Extraire le diff
    print("1 Extraction du diff...")
    diff_files = extract_diff(repo_name, pr_number)

    # Étape 2 : Parser le diff
    print("2 Parsing du diff...")
    parsed_files = parse_diff(diff_files)

    # Étape 3 : Filtrer les fichiers
    print("3 Filtrage des fichiers...")
    filtered_files = filter_files(parsed_files, include_tests=include_tests)

    if not filtered_files:
        print("Aucun fichier pertinent a analyser")
        return {
            "pr_number": pr_number,
            "repo_name": repo_name,
            "total_issues": 0,
            "issues": [],
            "summary": "Aucun fichier de code a analyser."
        }

    # Étape 4 : Chunking si nécessaire
    print("4 Chunking du diff...")
    chunks = chunk_diff(filtered_files)

    # Étape 5 : Analyser chaque fichier
    print(f"\n5 Analyse de {len(filtered_files)} fichier(s) avec le LLM...\n")
    all_issues = []
    all_summaries = []

    for chunk in chunks:
        for file_data in chunk:
            result = analyze_file(file_data, pr_title)
            all_issues.extend(result.get("issues", []))
            if result.get("summary"):
                all_summaries.append(result["summary"])

    # Étape 6 : Générer le résumé global
    print(f"\n6 Generation du resume global...")
    if all_issues:
        summary_prompt = build_summary_prompt(all_issues, pr_title)
        global_summary = invoke_llm(
            prompt=summary_prompt,
            max_tokens=500
        )
    else:
        global_summary = "Aucun probleme detecte dans cette PR."

    # Étape 7 : Calcul du score de sévérité (REVUE-36)
    print(f"\n7 Calcul du score de severite...")
    scoring = calculate_severity_score(all_issues)
    score_report = generate_score_report(all_issues, repo_name, pr_number)

    print(f"\nAnalyse terminee — {len(all_issues)} probleme(s) au total")
    print(f"Score de risque : {scoring['score']}/100 — {scoring['risk_level']['emoji']} {scoring['risk_level']['level']}")

    return {
        "pr_number": pr_number,
        "repo_name": repo_name,
        "total_issues": len(all_issues),
        "issues": all_issues,
        "summary": global_summary,
        "scoring": scoring,
        "score_report": score_report
    }