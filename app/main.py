from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from dotenv import load_dotenv
import hmac
import hashlib
import os
from fastapi.responses import HTMLResponse

load_dotenv()

app = FastAPI()

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")


def verify_signature(payload: bytes, signature: str) -> bool:
    mac = hmac.new(WEBHOOK_SECRET.encode(), msg=payload, digestmod=hashlib.sha256)
    expected = f"sha256={mac.hexdigest()}"
    return hmac.compare_digest(expected, signature)


def process_pull_request(repo_name: str, pr_number: int, pr_title: str):
    """
    Orchestre l'analyse complète et automatique d'une PR
    Connecte le webhook a tout le flux de l'agent IA
    """
    print(f"\n🤖 DEBUT TRAITEMENT AUTOMATIQUE — PR #{pr_number} sur {repo_name}\n")

    try:
        from app.analyzer import analyze_pr
        from app.diff_parser import extract_diff, parse_diff
        from app.review_comment import post_all_comments
        from app.pr_labeler import apply_labels
        from app.pr_approval import submit_review
        from app.quality_report import generate_quality_report_json, save_quality_report

        # Etape 1 : Analyse complete (LLM + scoring + config repo)
        result = analyze_pr(repo_name=repo_name, pr_number=pr_number, pr_title=pr_title)

        # Etape 2 : Recuperer les diffs pour le mapping des lignes
        diff_files = extract_diff(repo_name, pr_number)
        parsed_files = parse_diff(diff_files)

        # Etape 3 : Poster les commentaires inline + resume + score
        post_all_comments(
            repo_name=repo_name,
            pr_number=pr_number,
            analysis_result=result,
            diff_files=parsed_files,
        )

        # Etape 4 : Appliquer les labels automatiques
        apply_labels(repo_name=repo_name, pr_number=pr_number, issues=result["issues"])

        # Etape 5 : Soumettre la review automatique (approve/request changes)
        submit_review(repo_name=repo_name, pr_number=pr_number, issues=result["issues"])

        # Etape 6 : Generer et sauvegarder le rapport qualite (pour le dashboard)
        report_json = generate_quality_report_json(
            repo_name=repo_name,
            pr_number=pr_number,
            pr_title=pr_title,
            issues=result["issues"],
            scoring=result["scoring"],
            file_line_counts=result.get("file_line_counts", {}),
        )
        save_quality_report(report_json)

        print(f"\n✅ TRAITEMENT AUTOMATIQUE TERMINE — PR #{pr_number}\n")

    except Exception as e:
        print(
            f"\n❌ ERREUR lors du traitement automatique de la PR #{pr_number} : {str(e)}\n"
        )


MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 5


def process_pull_request_with_retry(repo_name: str, pr_number: int, pr_title: str):
    """
    Traite une PR avec mecanisme de retry en cas d'echec
    REVUE-50 : Ajouter un retry si le traitement echoue
    """
    import time

    for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
        try:
            print(f"\n🔄 Tentative {attempt}/{MAX_RETRY_ATTEMPTS} — PR #{pr_number}")
            process_pull_request(repo_name, pr_number, pr_title)
            print(f"✅ Traitement reussi a la tentative {attempt}")
            return

        except Exception as e:
            print(
                f"❌ Echec tentative {attempt}/{MAX_RETRY_ATTEMPTS} — PR #{pr_number} : {str(e)}"
            )

            if attempt < MAX_RETRY_ATTEMPTS:
                wait_time = RETRY_DELAY_SECONDS * attempt
                print(f"⏳ Nouvelle tentative dans {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(
                    f"🚨 ABANDON apres {MAX_RETRY_ATTEMPTS} tentatives — PR #{pr_number}"
                )


SUPPORTED_PR_ACTIONS = ["opened", "synchronize", "reopened", "ready_for_review"]


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    # Recuperer la signature GitHub
    signature = request.headers.get("X-Hub-Signature-256")
    if not signature:
        raise HTTPException(status_code=400, detail="Signature manquante")

    # Valider la signature HMAC
    payload = await request.body()
    if not verify_signature(payload, signature):
        raise HTTPException(status_code=401, detail="Signature invalide")

    # Parser le payload
    data = await request.json()
    event = request.headers.get("X-GitHub-Event")
    delivery_id = request.headers.get("X-GitHub-Delivery", "unknown")

    print(f"📨 Webhook recu — Event: {event} — Delivery ID: {delivery_id}")

    # Traiter uniquement les evenements pull_request
    if event == "pull_request":
        action = data.get("action")

        # REVUE-50 : Elargir les actions ecoutees (pas seulement opened/synchronize)
        if action in SUPPORTED_PR_ACTIONS:
            pr_number = data["pull_request"]["number"]
            repo_name = data["repository"]["full_name"]
            pr_title = data["pull_request"]["title"]

            print(f"✅ PR #{pr_number} détectée sur {repo_name} - Action: {action}")

            # Lancer le traitement complet en arriere-plan avec retry (REVUE-50)
            background_tasks.add_task(
                process_pull_request_with_retry, repo_name, pr_number, pr_title
            )

            return {"message": f"PR #{pr_number} en cours d'analyse (action: {action})"}
        else:
            print(f"ℹ️ Action ignoree : {action} (non supportee)")

    return {"message": "Événement ignoré"}


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(repo: str = None):
    """
    Dashboard de métriques de revue de code
    REVUE-46 : Filtrable par repository
    """
    from app.dashboard import (
        get_all_reports,
        filter_reports_by_repo,
        calculate_dashboard_stats,
        generate_dashboard_html,
    )

    all_reports = get_all_reports()
    filtered_reports = filter_reports_by_repo(all_reports, repo)
    stats = calculate_dashboard_stats(filtered_reports)
    html = generate_dashboard_html(stats, filtered_reports, repo)
    return html


@app.get("/dashboard/pr/{pr_number}", response_class=HTMLResponse)
async def dashboard_pr_detail(pr_number: int, repo: str = None):
    """
    Page de détail complète pour une PR analysée specifique
    """
    from app.dashboard import get_all_reports, get_report_by_pr, generate_pr_detail_html

    all_reports = get_all_reports()
    report = get_report_by_pr(all_reports, pr_number, repo)
    html = generate_pr_detail_html(report)
    return html
