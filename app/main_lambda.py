from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from dotenv import load_dotenv
import hmac
import hashlib
import os

load_dotenv()

app = FastAPI()

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")


def verify_signature(payload: bytes, signature: str) -> bool:
    mac = hmac.new(WEBHOOK_SECRET.encode(), msg=payload, digestmod=hashlib.sha256)
    expected = f"sha256={mac.hexdigest()}"
    return hmac.compare_digest(expected, signature)


SUPPORTED_PR_ACTIONS = ["opened", "synchronize", "reopened", "ready_for_review"]


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    from app.main import process_pull_request_with_retry

    signature = request.headers.get("X-Hub-Signature-256")
    if not signature:
        raise HTTPException(status_code=400, detail="Signature manquante")

    payload = await request.body()
    if not verify_signature(payload, signature):
        raise HTTPException(status_code=401, detail="Signature invalide")

    data = await request.json()
    event = request.headers.get("X-GitHub-Event")

    if event == "pull_request":
        action = data.get("action")
        if action in SUPPORTED_PR_ACTIONS:
            pr_number = data["pull_request"]["number"]
            repo_name = data["repository"]["full_name"]
            pr_title = data["pull_request"]["title"]

            background_tasks.add_task(
                process_pull_request_with_retry, repo_name, pr_number, pr_title
            )

            return {"message": f"PR #{pr_number} en cours d'analyse"}

    return {"message": "Evenement ignore"}