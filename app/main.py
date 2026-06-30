from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv
import hmac
import hashlib
import os
from fastapi.responses import HTMLResponse
from app.dashboard import get_all_reports, calculate_dashboard_stats, generate_dashboard_html

load_dotenv()

app = FastAPI()

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")

def verify_signature(payload: bytes, signature: str) -> bool:
    mac = hmac.new(
        WEBHOOK_SECRET.encode(),
        msg=payload,
        digestmod=hashlib.sha256
    )
    expected = f"sha256={mac.hexdigest()}"
    return hmac.compare_digest(expected, signature)

@app.post("/webhook")
async def webhook(request: Request):
    # Récupérer la signature GitHub
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

    # Traiter uniquement les événements pull_request
    if event == "pull_request":
        action = data.get("action")
        if action in ["opened", "synchronize"]:
            pr_number = data["pull_request"]["number"]
            repo_name = data["repository"]["full_name"]
            print(f"✅ PR #{pr_number} détectée sur {repo_name} - Action: {action}")
            return {"message": f"PR #{pr_number} en cours d'analyse"}

    return {"message": "Événement ignoré"}
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """
    Dashboard de métriques de revue de code
    REVUE-46 : Développer le dashboard de métriques de revue
    """
    reports = get_all_reports()
    stats = calculate_dashboard_stats(reports)
    html = generate_dashboard_html(stats)
    return html