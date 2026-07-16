from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Response, Cookie
from dotenv import load_dotenv
import hmac
import hashlib
import os
from fastapi.responses import HTMLResponse, RedirectResponse
import httpx
import secrets as py_secrets
from sqlalchemy.orm import Session
from app.database import get_db, User, UserRepo, SessionLocal
from app.auth_utils import hash_password, verify_password, create_access_token, decode_access_token, generate_reset_token, verify_reset_token, consume_reset_token, send_reset_email

load_dotenv()

app = FastAPI()

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
OAUTH_CLIENT_ID = os.getenv("GITHUB_OAUTH_CLIENT_ID")
OAUTH_CLIENT_SECRET = os.getenv("GITHUB_OAUTH_CLIENT_SECRET")
OAUTH_REDIRECT_URI = "https://agent-revue-app.mangocliff-bd24028f.eastus.azurecontainerapps.io/auth/callback"

# Stockage temporaire en memoire des tokens, un par utilisateur (session_id -> token)
user_sessions = {}


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


@app.get("/auth/login")
async def auth_login(response: Response):
    """
    Redirige vers GitHub pour connexion OAuth
    Cree un cookie de session unique pour cet utilisateur
    """
    session_id = py_secrets.token_urlsafe(32)

    github_auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={OAUTH_CLIENT_ID}"
        f"&redirect_uri={OAUTH_REDIRECT_URI}"
        f"&state={session_id}"
        f"&scope=repo"
    )

    redirect = RedirectResponse(github_auth_url)
    redirect.set_cookie(key="session_id", value=session_id, httponly=True, max_age=3600)
    return redirect


@app.get("/auth/callback")
async def auth_callback(
    code: str = None, state: str = None, session_id: str = Cookie(None)
):
    """
    Recoit le retour de GitHub apres connexion
    Echange le code temporaire contre un token d'acces
    Stocke le token dans LA session precise de cet utilisateur
    """
    if not code:
        return {"error": "Code manquant"}

    # Utilise le state (envoye a GitHub) ou le cookie comme identifiant de session
    effective_session_id = state or session_id
    if not effective_session_id:
        return {"error": "Session invalide"}

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": OAUTH_CLIENT_ID,
                "client_secret": OAUTH_CLIENT_SECRET,
                "code": code,
                "redirect_uri": OAUTH_REDIRECT_URI,
            },
        )
        data = response.json()
        access_token = data.get("access_token")

        if not access_token:
            return {"error": "Impossible d'obtenir le token", "details": data}

        user_sessions[effective_session_id] = {"access_token": access_token}

    redirect = RedirectResponse("/repos")
    redirect.set_cookie(
        key="session_id", value=effective_session_id, httponly=True, max_age=3600
    )
    return redirect


@app.get("/repos", response_class=HTMLResponse)
async def list_repos(session_id: str = Cookie(None)):
    """
    Liste tous les repos de l'utilisateur connecte via GitHub OAuth
    Indique lesquels ont deja l'agent installe
    Utilise LA session precise de cet utilisateur (cookie)
    """
    if not session_id or session_id not in user_sessions:
        return RedirectResponse("/auth/login")

    access_token = user_sessions[session_id]["access_token"]

    from app.dashboard import render_page_shell

    async with httpx.AsyncClient() as client:
        # Endpoint specifique GitHub App : lister les installations de l'utilisateur
        install_resp = await client.get(
            "https://api.github.com/user/installations",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
        )
        installations_data = install_resp.json()

        repos = []
        for installation in installations_data.get("installations", []):
            inst_id = installation["id"]
            repos_resp = await client.get(
                f"https://api.github.com/user/installations/{inst_id}/repositories",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            repos_data = repos_resp.json()
            repos.extend(repos_data.get("repositories", []))

        print(
            f"DEBUG: Nombre de repos recus de l'API: {len(repos) if isinstance(repos, list) else 'ERREUR - pas une liste'}"
        )
        print(f"DEBUG: Contenu brut: {repos}")

    installed_repos = set()
    try:
        from app.github_client import PRIVATE_KEY, APP_ID
        from github import GithubIntegration

        integration = GithubIntegration(APP_ID, PRIVATE_KEY)
        installation_id = int(os.getenv("GITHUB_INSTALLATION_ID"))
        install_token = integration.get_access_token(installation_id).token

        async with httpx.AsyncClient() as install_client:
            install_response = await install_client.get(
                "https://api.github.com/installation/repositories",
                headers={
                    "Authorization": f"Bearer {install_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            install_data = install_response.json()
            for repo in install_data.get("repositories", []):
                installed_repos.add(repo["full_name"])
    except Exception as e:
        print(f"Erreur recuperation repos installes : {str(e)}")

    rows = ""
    for repo in repos:
        full_name = repo.get("full_name", "")
        is_installed = full_name in installed_repos
        badge = (
            '<span class="badge clean">✅ Installé</span>'
            if is_installed
            else '<span class="badge medium">⚪ Non installé</span>'
        )
        install_link = (
            '<a href="https://github.com/apps/agent-revue-code/installations/new" target="_blank" class="view-btn">Installer</a>'
            if not is_installed
            else ""
        )
        rows += f"""
        <tr>
          <td>{full_name}</td>
          <td>{badge}</td>
          <td>{install_link}</td>
        </tr>"""

    body = f"""
  <div class="topbar">
    <div class="brand">
      <div class="brand-mark">AI</div>
      <div class="brand-text"><h1>Vos Repositories GitHub</h1></div>
    </div>
  </div>
  <a class="back-link" href="/dashboard">← Retour au dashboard</a>
  <div class="panel" style="margin-top:16px;">
    <table class="pr-table">
      <tr><th>Repository</th><th>Statut</th><th></th></tr>
      {rows}
    </table>
  </div>
"""
    return render_page_shell("Vos Repositories", body)

@app.get("/auth/register", response_class=HTMLResponse)
async def register_page():
    """
    Affiche le formulaire d'inscription
    """
    extra_head = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  .auth-page * { font-family: 'Inter', sans-serif !important; }
  .auth-page .auth-title {
    font-family: 'Poppins', sans-serif !important;
    font-size: 32px;
    font-weight: 800;
    text-align: center;
    margin-bottom: 6px;
    background: linear-gradient(120deg, var(--text) 0%, var(--accent) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  .auth-page .auth-subtitle {
    text-align: center;
    color: var(--text-dim);
    font-size: 14px;
    margin-bottom: 28px;
  }
  .auth-page .auth-brand {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    margin-bottom: 24px;
  }
  .auth-page .auth-brand .brand-mark {
    width: 40px; height: 40px; font-size: 17px;
  }
  .auth-page .auth-brand span {
    font-family: 'Poppins', sans-serif;
    font-weight: 700;
    font-size: 15px;
    color: var(--text);
  }
  .auth-page input {
    font-family: 'Inter', sans-serif !important;
    transition: border-color 0.2s ease;
  }
  .auth-page input:focus {
    outline: none;
    border-color: var(--accent) !important;
  }
  .auth-page .view-btn {
    background: var(--accent);
    color: #06090c;
    font-weight: 700;
    border: none;
    font-family: 'Poppins', sans-serif !important;
    font-size: 14px;
    cursor: pointer;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
  }
  .auth-page .view-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(var(--accent-rgb), 0.35);
  }
</style>
"""

    from app.dashboard import render_page_shell

    body = """
  <div class="topbar" style="justify-content:flex-end;">
    <div class="theme-toggle" id="themeToggle" role="button" aria-label="Changer de theme">
      <svg id="themeIcon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></svg>
      <span id="themeLabel">Mode nuit</span>
    </div>
  </div>
  <div class="auth-page">
  <div class="panel" style="max-width:420px; margin: 60px auto; padding: 40px 36px;">
    <div class="auth-brand">
      <div class="brand-mark">AI</div>
      <span>Agent Revue de Code</span>
    </div>
    <div class="auth-title">Créer un compte</div>
    <form method="POST" action="/auth/register">
      <div style="margin-bottom:18px;">
        <label style="display:block; margin-bottom:6px; font-size:13px; font-weight:600; color:var(--text-dim);">Nom d'utilisateur</label>
        <input type="text" name="username" required placeholder="Mohamed Badis" style="width:100%; padding:12px 14px; border-radius:10px; border:1.5px solid var(--grid-line); background:var(--bg-panel-2); color:var(--text); font-size:14px; box-sizing:border-box;">
      </div>
      <div style="margin-bottom:18px;">
        <label style="display:block; margin-bottom:6px; font-size:13px; font-weight:600; color:var(--text-dim);">Email</label>
        <input type="email" name="email" required placeholder="vous@smartovate.com" style="width:100%; padding:12px 14px; border-radius:10px; border:1.5px solid var(--grid-line); background:var(--bg-panel-2); color:var(--text); font-size:14px; box-sizing:border-box;">
      </div>
      <div style="margin-bottom:24px;">
        <label style="display:block; margin-bottom:6px; font-size:13px; font-weight:600; color:var(--text-dim);">Mot de passe</label>
        <input type="password" name="password" required placeholder="••••••••" style="width:100%; padding:12px 14px; border-radius:10px; border:1.5px solid var(--grid-line); background:var(--bg-panel-2); color:var(--text); font-size:14px; box-sizing:border-box;">
      </div>
      <button type="submit" class="view-btn" style="width:100%; padding:13px; border-radius:10px; font-size:15px;">S'inscrire →</button>
    </form>
    <p style="margin-top:20px; text-align:center; font-size:13.5px; color:var(--text-dim);">
      Déjà un compte ? <a href="/auth/user-login" style="font-weight:600;">Se connecter</a>
    </p>
  </div>
  </div>
"""
    return render_page_shell("Inscription", body, extra_head)

@app.post("/auth/register")
async def register(request: Request):
    """
    Cree un nouveau compte utilisateur
    """
    form = await request.form()
    username = form.get("username")
    email = form.get("email")
    password = form.get("password")

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            return {"error": "Cet email est deja utilise"}

        new_user = User(email=email, username=username, password_hash=hash_password(password))
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        token = create_access_token(new_user.id, new_user.email, new_user.username)
        redirect = RedirectResponse("/dashboard", status_code=303)
        redirect.set_cookie(key="auth_token", value=token, httponly=True, max_age=86400)
        return redirect
    finally:
        db.close()


@app.get("/auth/user-login", response_class=HTMLResponse)
async def user_login_page():
    """
    Affiche le formulaire de connexion
    """
    extra_head = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  .auth-page * { font-family: 'Inter', sans-serif !important; }
  .auth-page .auth-title {
    font-family: 'Poppins', sans-serif !important;
    font-size: 32px;
    font-weight: 800;
    text-align: center;
    margin-bottom: 6px;
    background: linear-gradient(120deg, var(--text) 0%, var(--accent) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  .auth-page .auth-subtitle {
    text-align: center;
    color: var(--text-dim);
    font-size: 14px;
    margin-bottom: 28px;
  }
  .auth-page .auth-brand {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    margin-bottom: 24px;
  }
  .auth-page .auth-brand .brand-mark {
    width: 40px; height: 40px; font-size: 17px;
  }
  .auth-page .auth-brand span {
    font-family: 'Poppins', sans-serif;
    font-weight: 700;
    font-size: 15px;
    color: var(--text);
  }
  .auth-page input {
    font-family: 'Inter', sans-serif !important;
    transition: border-color 0.2s ease;
  }
  .auth-page input:focus {
    outline: none;
    border-color: var(--accent) !important;
  }
  .auth-page .view-btn {
    background: var(--accent);
    color: #06090c;
    font-weight: 700;
    border: none;
    font-family: 'Poppins', sans-serif !important;
    font-size: 14px;
    cursor: pointer;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
  }
  .auth-page .view-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(var(--accent-rgb), 0.35);
  }
</style>
"""

    from app.dashboard import render_page_shell

    body = """
  <div class="topbar" style="justify-content:flex-end;">
    <div class="theme-toggle" id="themeToggle" role="button" aria-label="Changer de theme">
      <svg id="themeIcon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></svg>
      <span id="themeLabel">Mode nuit</span>
    </div>
  </div>
  <div class="auth-page">
  <div class="panel" style="max-width:420px; margin: 60px auto; padding: 40px 36px;">
    <div class="auth-brand">
      <div class="brand-mark">AI</div>
      <span>Agent Revue de Code</span>
    </div>
    <div class="auth-title">Bon retour</div>
    <form method="POST" action="/auth/user-login">
      <div style="margin-bottom:18px;">
        <label style="display:block; margin-bottom:6px; font-size:13px; font-weight:600; color:var(--text-dim);">Email</label>
        <input type="email" name="email" required placeholder="vous@smartovate.com" style="width:100%; padding:12px 14px; border-radius:10px; border:1.5px solid var(--grid-line); background:var(--bg-panel-2); color:var(--text); font-size:14px; box-sizing:border-box;">
      </div>
      <div style="margin-bottom:24px;">
        <label style="display:block; margin-bottom:6px; font-size:13px; font-weight:600; color:var(--text-dim);">Mot de passe</label>
        <input type="password" name="password" required placeholder="••••••••" style="width:100%; padding:12px 14px; border-radius:10px; border:1.5px solid var(--grid-line); background:var(--bg-panel-2); color:var(--text); font-size:14px; box-sizing:border-box;">
      </div>
      <button type="submit" class="view-btn" style="width:100%; padding:13px; border-radius:10px; font-size:15px;">Se connecter →</button>
    </form>
    <p style="margin-top:12px; text-align:center; font-size:13px;">
      <a href="/auth/forgot-password" style="color:var(--text-dim);">Mot de passe oublié ?</a>
    </p>
    <p style="margin-top:12px; text-align:center; font-size:13.5px; color:var(--text-dim);">
      Pas de compte ? <a href="/auth/register" style="font-weight:600;">S'inscrire</a>
    </p>
  </div>
  </div>
"""
    return render_page_shell("Connexion", body, extra_head)

@app.post("/auth/user-login")
async def user_login(request: Request):
    """
    Verifie les identifiants et connecte l'utilisateur
    """
    form = await request.form()
    email = form.get("email")
    password = form.get("password")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user or not verify_password(password, user.password_hash):
            return {"error": "Email ou mot de passe incorrect"}

        token = create_access_token(user.id, user.email, user.username)
        redirect = RedirectResponse("/dashboard", status_code=303)
        redirect.set_cookie(key="auth_token", value=token, httponly=True, max_age=86400)
        return redirect
    finally:
        db.close()

@app.get("/my-repos", response_class=HTMLResponse)
async def my_repos_page(auth_token: str = Cookie(None)):
    """
    Page de gestion des repos personnels de l'utilisateur connecte
    """
    if not auth_token:
        return RedirectResponse("/auth/user-login")

    payload = decode_access_token(auth_token)
    if not payload:
        return RedirectResponse("/auth/user-login")

    from app.dashboard import render_page_shell

    db = SessionLocal()
    try:
        user_repos = db.query(UserRepo).filter(UserRepo.owner_user_id == payload["user_id"]).all()
    finally:
        db.close()

    rows = ""
    for r in user_repos:
        rows += f"""
        <tr>
          <td>{r.repo_full_name}</td>
          <td>{r.added_at.strftime('%Y-%m-%d')}</td>
        </tr>"""
    if not rows:
        rows = '<tr><td colspan="2"><div class="empty-state">Aucun repository ajoute pour le moment.</div></td></tr>'

    body = f"""
  <div class="topbar" style="justify-content:flex-end;">
    <div class="theme-toggle" id="themeToggle" role="button" aria-label="Changer de theme">
      <svg id="themeIcon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></svg>
      <span id="themeLabel">Mode nuit</span>
    </div>
  </div>

  <a class="back-link" href="/dashboard">← Retour au dashboard</a>

  <div class="panel" style="max-width:600px; margin: 24px auto;">
    <div class="panel-head"><div class="panel-title">Ajouter un repository</div></div>
    <form method="POST" action="/my-repos/add">
      <div style="margin-bottom:16px;">
        <label style="display:block; margin-bottom:6px; font-size:13px; font-weight:600; color:var(--text-dim);">Nom complet du repository (owner/repo)</label>
        <input type="text" name="repo_full_name" required placeholder="mohamedbadishajji/mon-repo" style="width:100%; padding:12px 14px; border-radius:10px; border:1.5px solid var(--grid-line); background:var(--bg-panel-2); color:var(--text); font-size:14px; box-sizing:border-box;">
      </div>
      <button type="submit" class="view-btn" style="padding:12px 24px; border-radius:10px;">Verifier et ajouter →</button>
    </form>
  </div>

  <div class="panel" style="max-width:600px; margin: 24px auto;">
    <div class="panel-head"><div class="panel-title">Mes repositories ({len(user_repos)})</div></div>
    <table class="pr-table">
      <tr><th>Repository</th><th>Ajoute le</th></tr>
      {rows}
    </table>
  </div>
"""
    return render_page_shell("Mes Repositories", body)


@app.post("/my-repos/add")
async def add_my_repo(request: Request, auth_token: str = Cookie(None)):
    """
    Verifie via GitHub OAuth que l'utilisateur a bien acces a ce repo,
    puis l'ajoute a son compte
    """
    if not auth_token:
        return RedirectResponse("/auth/user-login")

    payload = decode_access_token(auth_token)
    if not payload:
        return RedirectResponse("/auth/user-login")

    form = await request.form()
    repo_full_name = form.get("repo_full_name", "").strip()

    if not repo_full_name or "/" not in repo_full_name:
        return {"error": "Format invalide. Utilisez: owner/repo"}

    # Verification technique : ce repo appartient-il vraiment a l'installation
    # de la GitHub App ? (methode fiable, deja testee avec succes)
    try:
        from app.github_client import PRIVATE_KEY, APP_ID
        from github import GithubIntegration

        integration = GithubIntegration(APP_ID, PRIVATE_KEY)
        installation_id = int(os.getenv("GITHUB_INSTALLATION_ID"))
        install_token = integration.get_access_token(installation_id).token

        async with httpx.AsyncClient() as client:
            check_response = await client.get(
                f"https://api.github.com/repos/{repo_full_name}",
                headers={
                    "Authorization": f"Bearer {install_token}",
                    "Accept": "application/vnd.github+json",
                },
            )

        if check_response.status_code != 200:
            return {"error": f"Ce repository n'est pas accessible ou l'agent n'y est pas installe. Installez d'abord l'app via le bouton du dashboard."}

    except Exception as e:
        return {"error": f"Erreur de verification : {str(e)}"}

    db = SessionLocal()
    try:
        existing = db.query(UserRepo).filter(UserRepo.repo_full_name == repo_full_name).first()
        if existing:
            return {"error": "Ce repository est deja associe a un compte"}

        new_repo = UserRepo(repo_full_name=repo_full_name, owner_user_id=payload["user_id"])
        db.add(new_repo)
        db.commit()
    finally:
        db.close()

    return RedirectResponse("/my-repos", status_code=303)

@app.get("/auth/logout")
async def logout():
    """
    Deconnecte l'utilisateur et le redirige vers la page de connexion
    """
    redirect = RedirectResponse("/auth/user-login", status_code=302)
    redirect.delete_cookie(key="auth_token", path="/")
    return redirect

@app.get("/auth/forgot-password", response_class=HTMLResponse)
async def forgot_password_page():
    """
    Affiche le formulaire de demande de reinitialisation
    """
    from app.dashboard import render_page_shell

    body = """
  <div class="topbar" style="justify-content:flex-end;">
    <div class="theme-toggle" id="themeToggle" role="button" aria-label="Changer de theme">
      <svg id="themeIcon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></svg>
      <span id="themeLabel">Mode nuit</span>
    </div>
  </div>
  <div class="auth-page">
  <div class="panel" style="max-width:420px; margin: 60px auto; padding: 40px 36px;">
    <div class="auth-brand">
      <div class="brand-mark">AI</div>
      <span>Agent Revue de Code</span>
    </div>
    <div class="auth-title">Mot de passe oublie</div>
    <div class="auth-subtitle">Recevez un lien de reinitialisation par email</div>
    <form method="POST" action="/auth/forgot-password">
      <div style="margin-bottom:24px;">
        <label style="display:block; margin-bottom:6px; font-size:13px; font-weight:600; color:var(--text-dim);">Email</label>
        <input type="email" name="email" required placeholder="vous@smartovate.com" style="width:100%; padding:12px 14px; border-radius:10px; border:1.5px solid var(--grid-line); background:var(--bg-panel-2); color:var(--text); font-size:14px; box-sizing:border-box;">
      </div>
      <button type="submit" class="view-btn" style="width:100%; padding:13px; border-radius:10px; font-size:15px;">Envoyer le lien →</button>
    </form>
    <p style="margin-top:20px; text-align:center; font-size:13.5px; color:var(--text-dim);">
      <a href="/auth/user-login" style="font-weight:600;">← Retour a la connexion</a>
    </p>
  </div>
  </div>
"""
    return render_page_shell("Mot de passe oublie", body)


@app.post("/auth/forgot-password", response_class=HTMLResponse)
async def forgot_password(request: Request):
    """
    Genere un token et envoie l'email de reinitialisation
    """
    form = await request.form()
    email = form.get("email")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            token = generate_reset_token(user.id)
            reset_link = f"https://agent-revue-app.mangocliff-bd24028f.eastus.azurecontainerapps.io/auth/reset-password?token={token}"
            send_reset_email(user.email, reset_link)
    finally:
        db.close()

    from app.dashboard import render_page_shell
    body = """
  <div class="auth-page">
  <div class="panel" style="max-width:420px; margin: 60px auto; padding: 40px 36px; text-align:center;">
    <div class="auth-title">Email envoye ✅</div>
    <p style="color:var(--text-dim);">Si un compte existe avec cet email, un lien de reinitialisation vient de vous etre envoye.</p>
    <p style="margin-top:20px;"><a href="/auth/user-login" style="font-weight:600;">← Retour a la connexion</a></p>
  </div>
  </div>
"""
    return render_page_shell("Email envoye", body)


@app.get("/auth/reset-password", response_class=HTMLResponse)
async def reset_password_page(token: str = None):
    """
    Affiche le formulaire de nouveau mot de passe
    """
    from app.dashboard import render_page_shell

    if not token or not verify_reset_token(token):
        body = """
  <div class="auth-page">
  <div class="panel" style="max-width:420px; margin: 60px auto; padding: 40px 36px; text-align:center;">
    <div class="auth-title">Lien invalide</div>
    <p style="color:var(--text-dim);">Ce lien de reinitialisation est invalide ou a expire.</p>
    <p style="margin-top:20px;"><a href="/auth/forgot-password" style="font-weight:600;">Demander un nouveau lien</a></p>
  </div>
  </div>
"""
        return render_page_shell("Lien invalide", body)

    body = f"""
  <div class="auth-page">
  <div class="panel" style="max-width:420px; margin: 60px auto; padding: 40px 36px;">
    <div class="auth-title">Nouveau mot de passe</div>
    <div class="auth-subtitle">Choisissez un nouveau mot de passe</div>
    <form method="POST" action="/auth/reset-password">
      <input type="hidden" name="token" value="{token}">
      <div style="margin-bottom:24px;">
        <label style="display:block; margin-bottom:6px; font-size:13px; font-weight:600; color:var(--text-dim);">Nouveau mot de passe</label>
        <input type="password" name="password" required placeholder="••••••••" style="width:100%; padding:12px 14px; border-radius:10px; border:1.5px solid var(--grid-line); background:var(--bg-panel-2); color:var(--text); font-size:14px; box-sizing:border-box;">
      </div>
      <button type="submit" class="view-btn" style="width:100%; padding:13px; border-radius:10px; font-size:15px;">Reinitialiser →</button>
    </form>
  </div>
  </div>
"""
    return render_page_shell("Nouveau mot de passe", body)


@app.post("/auth/reset-password")
async def reset_password(request: Request):
    """
    Verifie le token et met a jour le mot de passe
    """
    form = await request.form()
    token = form.get("token")
    password = form.get("password")

    user_id = verify_reset_token(token)
    if not user_id:
        return {"error": "Token invalide ou expire"}

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        user.password_hash = hash_password(password)
        db.commit()
    finally:
        db.close()

    consume_reset_token(token)
    return RedirectResponse("/auth/user-login", status_code=303)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(repo: str = None, auth_token: str = Cookie(None)):
    """
    Dashboard de metriques de revue de code
    REVUE-46 : Filtrable par repository ET par utilisateur connecte
    """
    from app.dashboard import get_all_reports, filter_reports_by_repo, calculate_dashboard_stats, generate_dashboard_html

    all_reports = get_all_reports()

    # Si un utilisateur est connecte, filtrer sur SES repos uniquement
    if auth_token:
        payload = decode_access_token(auth_token)
        if payload:
            db = SessionLocal()
            try:
                user_id = payload["user_id"]
                user_repos = db.query(UserRepo).filter(UserRepo.owner_user_id == user_id).all()
                user_repo_names = {r.repo_full_name for r in user_repos}

                if user_repo_names:
                    all_reports = [r for r in all_reports if r.get("repo_name") in user_repo_names]
                else:
                    all_reports = []
            finally:
                db.close()

    fcurrent_user_email = None
    if auth_token:
        payload = decode_access_token(auth_token)
        if payload:
            current_user_email = payload.get("username") or payload.get("email")
            db = SessionLocal()
            try:
                user_id = payload["user_id"]
                user_repos = db.query(UserRepo).filter(UserRepo.owner_user_id == user_id).all()
                user_repo_names = {r.repo_full_name for r in user_repos}

                if user_repo_names:
                    all_reports = [r for r in all_reports if r.get("repo_name") in user_repo_names]
                else:
                    all_reports = []
            finally:
                db.close()

    filtered_reports = filter_reports_by_repo(all_reports, repo)
    stats = calculate_dashboard_stats(filtered_reports)
    html = generate_dashboard_html(stats, filtered_reports, repo, current_user_email)
    from fastapi.responses import HTMLResponse as HTMLResp
    response = HTMLResp(content=html)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response


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
