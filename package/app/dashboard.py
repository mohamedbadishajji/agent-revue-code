from dotenv import load_dotenv

load_dotenv()
import os
import json
import glob
from datetime import datetime
from collections import defaultdict

REPORTS_DIR = "reports"
ESTIMATED_TIME_PER_REVIEW_MINUTES = 15


def get_blob_service_client():
    """
    Crée le client Azure Blob Storage si les credentials sont configurés
    """
    account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
    account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")

    if not account_name or not account_key:
        return None

    connection_string = (
        f"DefaultEndpointsProtocol=https;"
        f"AccountName={account_name};"
        f"AccountKey={account_key};"
        f"EndpointSuffix=core.windows.net"
    )

    try:
        from azure.storage.blob import BlobServiceClient

        return BlobServiceClient.from_connection_string(connection_string)
    except Exception as e:
        print(f"   ⚠️ Erreur connexion Azure Blob Storage : {str(e)}")
        return None


def get_all_reports() -> list:
    """
    Charge tous les rapports JSON
    REVUE-46 : Priorise Azure Blob Storage (persistant), fallback local
    """
    reports = []

    # Priorité 1 : Azure Blob Storage
    blob_service = get_blob_service_client()
    if blob_service:
        try:
            container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "reports")
            container_client = blob_service.get_container_client(container_name)

            for blob in container_client.list_blobs():
                try:
                    blob_client = container_client.get_blob_client(blob.name)
                    content = blob_client.download_blob().readall()
                    reports.append(json.loads(content))
                except Exception as e:
                    print(f"   ⚠️ Erreur lecture blob {blob.name} : {str(e)}")

            if reports:
                return reports
        except Exception as e:
            print(
                f"   ⚠️ Erreur listing Azure Blob Storage : {str(e)} — fallback local"
            )

    # Priorité 2 : Stockage local (développement)
    if not os.path.exists(REPORTS_DIR):
        return reports

    pattern = os.path.join(REPORTS_DIR, "*.json")
    for filepath in glob.glob(pattern):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                reports.append(json.load(f))
        except Exception as e:
            print(f"   Erreur lecture {filepath} : {str(e)}")

    return reports


def get_all_repos(reports: list) -> list:
    """Retourne la liste triee des repos uniques presents dans les rapports"""
    repos = sorted(set(r.get("repo_name", "unknown") for r in reports))
    return repos


def filter_reports_by_repo(reports: list, repo_name: str = None) -> list:
    """Filtre les rapports pour ne garder que ceux d'un repo specifique"""
    if not repo_name or repo_name == "all":
        return reports
    return [r for r in reports if r.get("repo_name") == repo_name]


def get_pr_list(reports: list) -> list:
    """
    Construit la liste des PRs analysees, dedupliquee par (repo, pr_number)
    en gardant l'analyse la plus recente pour chaque PR
    """
    latest_by_pr = {}
    for r in reports:
        key = (r.get("repo_name"), r.get("pr_number"))
        existing = latest_by_pr.get(key)
        if not existing or r.get("analyzed_at", "") > existing.get("analyzed_at", ""):
            latest_by_pr[key] = r

    pr_list = list(latest_by_pr.values())
    pr_list.sort(key=lambda x: x.get("analyzed_at", ""), reverse=True)
    return pr_list


def get_report_by_pr(reports: list, pr_number: int, repo_name: str = None) -> dict:
    """Recupere le rapport le plus recent pour une PR donnee"""
    matching = [r for r in reports if r.get("pr_number") == pr_number]
    if repo_name:
        matching = [r for r in matching if r.get("repo_name") == repo_name]
    if not matching:
        return None
    matching.sort(key=lambda x: x.get("analyzed_at", ""), reverse=True)
    return matching[0]


BASE_MINUTES_PER_PR = 5
MINUTES_PER_LINE = 0.1

SEVERITY_TIME_WEIGHTS = {"critical": 8, "high": 5, "medium": 3, "low": 1}


def estimate_review_time_minutes(report: dict) -> float:
    """
    Estime le temps qu'un reviewer humain aurait passe sur CETTE PR precise
    Formule : temps de base + temps de lecture (proportionnel aux VRAIES lignes modifiees)
              + temps d'investigation pondere par la severite de chaque probleme
    REVUE-46 : Calcul precis base sur les donnees reelles de la PR
    """
    minutes = BASE_MINUTES_PER_PR

    # Temps de lecture proportionnel au nombre REEL de lignes ajoutees
    file_line_counts = report.get("file_line_counts", {})
    if file_line_counts:
        total_lines = sum(file_line_counts.values())
    else:
        # Fallback pour les anciens rapports sans cette donnee
        num_files = len(report.get("file_metrics", {}))
        total_lines = num_files * 30

    minutes += total_lines * MINUTES_PER_LINE

    # Temps d'investigation pondere par la severite reelle de chaque probleme
    for issue in report.get("issues", []):
        severity = issue.get("severity", "low")
        minutes += SEVERITY_TIME_WEIGHTS.get(severity, 1)

    return round(minutes, 1)


def calculate_time_saved(reports_or_count) -> dict:
    """
    Calcule le temps total gagne
    Accepte soit une liste de rapports (calcul precis), soit un entier (fallback)
    """
    if isinstance(reports_or_count, list):
        total_minutes = sum(estimate_review_time_minutes(r) for r in reports_or_count)
    else:
        # Fallback si aucun rapport disponible (cas vide)
        total_minutes = 0

    hours = total_minutes // 60
    minutes = total_minutes % 60
    return {
        "total_minutes": total_minutes,
        "hours": hours,
        "minutes": minutes,
        "formatted": f"{hours}h {minutes}min" if hours > 0 else f"{minutes}min",
    }


def calculate_dashboard_stats(reports: list) -> dict:
    if not reports:
        return {
            "total_prs": 0,
            "average_score": 0,
            "total_issues": 0,
            "score_distribution": {},
            "type_distribution": {},
            "worst_files": [],
            "score_history": [],
            "time_saved": calculate_time_saved([]),
            "critical_count": 0,
            "approved_count": 0,
        }

    # Utiliser la liste dedupliquee pour les stats (une PR = un point de donnee)
    pr_list = get_pr_list(reports)

    total_prs = len(pr_list)
    total_score = sum(r.get("score", 0) for r in pr_list)
    average_score = round(total_score / total_prs, 1) if total_prs else 0
    total_issues = sum(r.get("total_issues", 0) for r in pr_list)

    score_distribution = defaultdict(int)
    for r in pr_list:
        score_distribution[r.get("risk_level", "UNKNOWN")] += 1

    type_distribution = defaultdict(int)
    for r in pr_list:
        for issue_type, count in r.get("type_metrics", {}).items():
            type_distribution[issue_type] += count

    file_issue_count = defaultdict(int)
    for r in pr_list:
        for file_path, metrics in r.get("file_metrics", {}).items():
            file_issue_count[file_path] += metrics.get("total_issues", 0)

    worst_files = sorted(file_issue_count.items(), key=lambda x: x[1], reverse=True)[:5]

    score_history = sorted(
        [
            {
                "pr_number": r.get("pr_number"),
                "score": r.get("score"),
                "date": r.get("analyzed_at", ""),
            }
            for r in pr_list
        ],
        key=lambda x: x["date"],
    )

    time_saved = calculate_time_saved(pr_list)
    critical_count = score_distribution.get("CRITICAL RISK", 0)
    approved_count = score_distribution.get("CLEAN", 0)

    return {
        "total_prs": total_prs,
        "average_score": average_score,
        "total_issues": total_issues,
        "score_distribution": dict(score_distribution),
        "type_distribution": dict(type_distribution),
        "worst_files": worst_files,
        "score_history": score_history,
        "time_saved": time_saved,
        "critical_count": critical_count,
        "approved_count": approved_count,
    }


def render_page_shell(title: str, body_content: str, extra_head: str = "") -> str:
    """
    Shell HTML commun (theme, fond anime, toggle jour/nuit) reutilise
    par la vue dashboard et la vue detail PR
    """
    now_str = datetime.now().strftime("%H:%M:%S")

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
{extra_head}
<style>
  :root {{
    --bg: #06090c;
    --bg-panel-rgb: 11,17,22;
    --bg-panel-2: #0e151b;
    --grid-line: #182026;
    --accent: #3da9ff;
    --accent-dim: #1d5fa8;
    --accent-rgb: 61,169,255;
    --amber: #ffb454;
    --red: #ff5c5c;
    --green: #3fb950;
    --text: #d7e3df;
    --text-dim: #5e7269;
    --mono: 'JetBrains Mono', 'SFMono-Regular', Consolas, monospace;
    --sans: 'Space Grotesk', -apple-system, sans-serif;
    --panel-blur: blur(14px);
    --panel-shadow: 0 4px 30px rgba(0,0,0,0.3);
    --particle-rgb: 61,169,255;
  }}
  html[data-theme="light"] {{
    --bg: #eef2f6;
    --bg-panel-rgb: 255,255,255;
    --bg-panel-2: #e3e9ef;
    --grid-line: #d4dce3;
    --accent: #1267d6;
    --accent-dim: #6fa8e8;
    --accent-rgb: 18,103,214;
    --amber: #c97a16;
    --red: #d6394a;
    --green: #1a8f4c;
    --text: #1c2733;
    --text-dim: #6b7a89;
    --panel-shadow: 0 4px 24px rgba(28,39,51,0.08);
    --particle-rgb: 18,103,214;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    -webkit-font-smoothing: antialiased;
    transition: background 0.35s ease, color 0.35s ease;
  }}
  body {{
    min-height: 100vh;
    padding: 28px 32px 60px;
    position: relative;
    overflow-x: hidden;
  }}
  #bg-canvas {{
    position: fixed;
    top: 0; left: 0;
    width: 100%; height: 100%;
    z-index: 0;
    pointer-events: none;
  }}
  .page {{ position: relative; z-index: 1; max-width: 1200px; margin: 0 auto; }}

  a {{ color: var(--accent); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}

  /* ── Header ── */
  .topbar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 18px;
    margin-bottom: 28px;
    gap: 16px;
    flex-wrap: wrap;
  }}
  .brand {{ display: flex; align-items: center; gap: 14px; }}
  .brand-mark {{
    width: 34px; height: 34px;
    border: 1.5px solid var(--accent);
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    color: var(--accent);
    font-family: var(--mono);
    font-weight: 700;
    font-size: 15px;
    box-shadow: 0 0 16px rgba(var(--accent-rgb),0.25);
    flex-shrink: 0;
  }}
  .brand-text h1 {{
    margin: 0; font-size: 17px; font-weight: 600; letter-spacing: 0.01em;
    background: linear-gradient(120deg, var(--text) 0%, var(--accent) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }}
  .header-actions {{
    display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  }}
  .status-pill {{
    display: flex; align-items: center; gap: 8px;
    font-family: var(--mono); font-size: 11.5px; color: var(--accent);
    border: 1px solid var(--accent-dim);
    background: rgba(var(--accent-rgb),0.08);
    padding: 7px 13px; border-radius: 100px;
    letter-spacing: 0.04em;
  }}
  .pulse-dot {{
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--accent);
    box-shadow: 0 0 8px var(--accent);
    animation: pulse 1.8s ease-in-out infinite;
  }}
  @keyframes pulse {{
    0%, 100% {{ opacity: 1; transform: scale(1); }}
    50% {{ opacity: 0.4; transform: scale(0.78); }}
  }}
  .theme-toggle, .repo-select {{
    display: flex; align-items: center; gap: 8px;
    font-family: var(--mono); font-size: 11px; color: var(--text-dim);
    border: 1px solid var(--grid-line);
    background: rgba(var(--bg-panel-rgb),0.55);
    backdrop-filter: var(--panel-blur);
    -webkit-backdrop-filter: var(--panel-blur);
    padding: 6px 12px; border-radius: 100px;
    cursor: pointer;
    user-select: none;
    transition: border-color 0.2s ease, color 0.2s ease;
  }}
  .theme-toggle:hover {{ border-color: var(--accent-dim); color: var(--accent); }}
  .theme-toggle svg {{ width: 14px; height: 14px; }}
  .repo-select select {{
    background: transparent;
    border: none;
    color: var(--text);
    font-family: var(--mono);
    font-size: 11px;
    outline: none;
    cursor: pointer;
  }}
  .repo-select select option {{ background: var(--bg); color: var(--text); }}
  .back-link {{
    font-family: var(--mono); font-size: 11.5px; color: var(--text-dim);
    display: inline-flex; align-items: center; gap: 6px;
  }}
  .back-link:hover {{ color: var(--accent); }}

  /* ── KPI strip ── */
  .kpi-strip {{
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 14px;
    margin-bottom: 22px;
  }}
  .kpi {{
    background: rgba(var(--bg-panel-rgb),0.55);
    backdrop-filter: var(--panel-blur);
    -webkit-backdrop-filter: var(--panel-blur);
    border-radius: 16px;
    padding: 20px 20px 18px;
    position: relative;
    opacity: 0;
    animation: rise 0.5s ease forwards;
    box-shadow: var(--panel-shadow);
  }}
  .kpi:nth-child(1) {{ animation-delay: 0.02s; }}
  .kpi:nth-child(2) {{ animation-delay: 0.08s; }}
  .kpi:nth-child(3) {{ animation-delay: 0.14s; }}
  .kpi:nth-child(4) {{ animation-delay: 0.20s; }}
  .kpi:nth-child(5) {{ animation-delay: 0.26s; }}
  @keyframes rise {{
    from {{ opacity: 0; transform: translateY(8px); }}
    to {{ opacity: 1; transform: translateY(0); }}
  }}
  .kpi-label {{
    font-family: var(--mono); font-size: 10.5px; text-transform: uppercase;
    letter-spacing: 0.09em; color: var(--text-dim); margin-bottom: 10px;
  }}
  .kpi-value {{
    font-family: var(--mono); font-size: 32px; font-weight: 700; color: var(--text);
    line-height: 1; display: flex; align-items: baseline; gap: 8px;
    letter-spacing: -0.01em;
  }}
  .kpi-value.accent {{ color: var(--accent); }}
  .kpi-value.warn {{ color: var(--amber); }}
  .kpi-sub {{ font-size: 11px; color: var(--text-dim); margin-top: 8px; }}
  .kpi-spark {{
    position: absolute; bottom: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, transparent, var(--accent), transparent);
    opacity: 0.5;
  }}

  /* ── Grid layout ── */
  .grid-2 {{
    display: grid; grid-template-columns: 1.4fr 1fr; gap: 16px; margin-bottom: 16px;
  }}
  .panel {{
    background: rgba(var(--bg-panel-rgb),0.55);
    backdrop-filter: var(--panel-blur);
    -webkit-backdrop-filter: var(--panel-blur);
    border-radius: 16px;
    padding: 20px 22px 16px;
    box-shadow: var(--panel-shadow);
    margin-bottom: 16px;
  }}
  .panel-head {{
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 14px;
  }}
  .panel-title {{
    font-family: var(--mono); font-size: 12px; text-transform: uppercase;
    letter-spacing: 0.08em; color: var(--text-dim); display: flex; align-items: center; gap: 8px;
  }}
  .panel-title::before {{
    content: ''; width: 3px; height: 12px; background: var(--accent); display: inline-block;
    box-shadow: 0 0 6px var(--accent);
  }}
  .chart-wrap {{ position: relative; height: 220px; }}

  .grid-3 {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 16px;
  }}

  /* ── File rows ── */
  .file-row {{ margin-bottom: 14px; }}
  .file-row:last-child {{ margin-bottom: 0; }}
  .file-row-top {{
    display: flex; justify-content: space-between; font-family: var(--mono);
    font-size: 12.5px; margin-bottom: 6px;
  }}
  .file-name {{ color: var(--text); }}
  .file-count {{ color: var(--amber); font-weight: 700; }}
  .file-bar-track {{
    height: 5px; background: var(--bg-panel-2); border-radius: 3px; overflow: hidden;
  }}
  .file-bar-fill {{
    height: 100%; background: linear-gradient(90deg, var(--accent-dim), var(--amber));
    border-radius: 3px; transition: width 0.6s ease;
  }}
  .empty-state {{
    color: var(--text-dim); font-family: var(--mono); font-size: 12px;
    text-align: center; padding: 30px 0;
  }}

  /* ── PR table ── */
  table.pr-table {{ width: 100%; border-collapse: collapse; font-family: var(--mono); font-size: 12.5px; }}
  table.pr-table th {{
    text-align: left; padding: 10px 12px; color: var(--text-dim);
    text-transform: uppercase; font-size: 10px; letter-spacing: 0.08em;
    border-bottom: 1px solid var(--grid-line);
  }}
  table.pr-table td {{
    padding: 12px; border-bottom: 1px solid var(--grid-line);
    vertical-align: middle;
  }}
  table.pr-table tr:last-child td {{ border-bottom: none; }}
  table.pr-table tr:hover td {{ background: rgba(var(--accent-rgb),0.05); }}
  .badge {{
    display: inline-block; padding: 3px 10px; border-radius: 100px;
    font-size: 10.5px; font-weight: 600; letter-spacing: 0.03em;
  }}
  .badge.critical {{ background: rgba(255,92,92,0.15); color: var(--red); }}
  .badge.high {{ background: rgba(255,138,61,0.15); color: #ff8a3d; }}
  .badge.medium {{ background: rgba(255,180,84,0.15); color: var(--amber); }}
  .badge.low {{ background: rgba(63,185,80,0.15); color: var(--green); }}
  .badge.clean {{ background: rgba(61,169,255,0.15); color: var(--accent); }}
  .view-btn {{
    font-family: var(--mono); font-size: 11px; color: var(--accent);
    border: 1px solid var(--accent-dim); border-radius: 100px;
    padding: 4px 12px; white-space: nowrap;
  }}
  .view-btn:hover {{ background: rgba(var(--accent-rgb),0.1); text-decoration: none; }}
  .repo-tag {{ color: var(--text-dim); font-size: 11px; }}

  /* ── Detail page ── */
  .issue-card {{
    background: rgba(var(--bg-panel-2),0.4);
    border-left: 3px solid var(--grid-line);
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 12px;
  }}
  .issue-card.critical {{ border-left-color: var(--red); }}
  .issue-card.high {{ border-left-color: #ff8a3d; }}
  .issue-card.medium {{ border-left-color: var(--amber); }}
  .issue-card.low {{ border-left-color: var(--green); }}
  .issue-head {{
    display: flex; align-items: center; gap: 10px; margin-bottom: 8px;
    font-family: var(--mono); font-size: 11.5px;
  }}
  .issue-loc {{ color: var(--text-dim); }}
  .issue-desc {{ font-size: 13.5px; margin-bottom: 6px; }}
  .issue-fix {{ font-size: 12px; color: var(--text-dim); }}
  .issue-fix b {{ color: var(--text); }}

  footer {{
    margin-top: 24px; text-align: center; font-family: var(--mono);
    font-size: 10.5px; color: var(--text-dim); letter-spacing: 0.04em;
  }}

  @media (max-width: 900px) {{
    .kpi-strip {{ grid-template-columns: repeat(2, 1fr); }}
    .grid-2, .grid-3 {{ grid-template-columns: 1fr; }}
    table.pr-table {{ font-size: 11px; }}
  }}
</style>
</head>
<body>
<canvas id="bg-canvas"></canvas>
<div class="page">
{body_content}
</div>

<script>
  // ── Theme toggle (dark / light) ──
  const ICONS = {{
    dark: '<circle cx="12" cy="12" r="4"></circle><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
    light: '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>'
  }};
  function applyTheme(theme) {{
    document.documentElement.setAttribute('data-theme', theme);
    const iconEl = document.getElementById('themeIcon');
    const labelEl = document.getElementById('themeLabel');
    if (iconEl) iconEl.innerHTML = theme === 'dark' ? ICONS.light : ICONS.dark;
    if (labelEl) labelEl.textContent = theme === 'dark' ? 'Mode jour' : 'Mode nuit';
    localStorage.setItem('dashboard-theme', theme);
  }}
  const savedTheme = localStorage.getItem('dashboard-theme') || 'dark';
  applyTheme(savedTheme);
  const toggleBtn = document.getElementById('themeToggle');
  if (toggleBtn) {{
    toggleBtn.addEventListener('click', () => {{
      const current = document.documentElement.getAttribute('data-theme') || 'dark';
      applyTheme(current === 'dark' ? 'light' : 'dark');
    }});
  }}

  const repoSelectEl = document.getElementById('repoSelect');
  if (repoSelectEl) {{
    repoSelectEl.addEventListener('change', function() {{
      const val = this.value;
      window.location.href = val === 'all' ? '/dashboard' : '/dashboard?repo=' + encodeURIComponent(val);
    }});
  }}

  // ── Fond animé : reseau de neurones couvrant toute la page ──
  (function() {{
    const canvas = document.getElementById('bg-canvas');
    const ctx = canvas.getContext('2d');
    let w, h, particles, docH;

    function getParticleColor() {{
      return getComputedStyle(document.documentElement).getPropertyValue('--particle-rgb').trim();
    }}

    function resize() {{
      docH = Math.max(document.body.scrollHeight, window.innerHeight);
      w = canvas.width = window.innerWidth;
      h = canvas.height = docH;
      canvas.style.height = docH + 'px';
    }}
    window.addEventListener('resize', resize);
    window.addEventListener('load', resize);
    resize();
    setTimeout(resize, 400);

    const DENSITY = 14000;
    function buildParticles() {{
      const COUNT = Math.min(140, Math.floor((w * h) / DENSITY));
      particles = Array.from({{ length: COUNT }}, () => ({{
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.35,
        vy: (Math.random() - 0.5) * 0.35,
        r: Math.random() * 1.6 + 0.8,
        pulse: Math.random() * Math.PI * 2
      }}));
    }}
    buildParticles();
    window.addEventListener('resize', buildParticles);

    function tick(t) {{
      const rgb = getParticleColor();
      ctx.clearRect(0, 0, w, h);
      for (let i = 0; i < particles.length; i++) {{
        const p = particles[i];
        p.x += p.vx; p.y += p.vy;
        if (p.x < -20) p.x = w + 20;
        if (p.x > w + 20) p.x = -20;
        if (p.y < -20) p.y = h + 20;
        if (p.y > h + 20) p.y = -20;

        const glow = 0.45 + Math.sin(t / 900 + p.pulse) * 0.25;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${{rgb}},${{glow}})`;
        ctx.shadowBlur = 6;
        ctx.shadowColor = `rgba(${{rgb}},0.6)`;
        ctx.fill();
        ctx.shadowBlur = 0;

        for (let j = i + 1; j < particles.length; j++) {{
          const q = particles[j];
          const dx = p.x - q.x, dy = p.y - q.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 150) {{
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(q.x, q.y);
            ctx.strokeStyle = `rgba(${{rgb}},${{(1 - dist / 150) * 0.22}})`;
            ctx.lineWidth = 1;
            ctx.stroke();
          }}
        }}
      }}
      requestAnimationFrame(tick);
    }}
    requestAnimationFrame(tick);
  }})();
</script>
</body>
</html>"""


def risk_badge_class(risk_level: str) -> str:
    mapping = {
        "CRITICAL RISK": "critical",
        "HIGH RISK": "high",
        "MEDIUM RISK": "medium",
        "LOW RISK": "low",
        "CLEAN": "clean",
    }
    return mapping.get(risk_level, "medium")


def generate_dashboard_html(
    stats: dict, reports: list = None, selected_repo: str = None
) -> str:
    reports = reports or []
    repos = get_all_repos(reports)
    pr_list = get_pr_list(reports)

    score_labels = json.dumps([f"PR #{h['pr_number']}" for h in stats["score_history"]])
    score_values = json.dumps([h["score"] for h in stats["score_history"]])
    risk_labels = json.dumps(list(stats["score_distribution"].keys()))
    risk_values = json.dumps(list(stats["score_distribution"].values()))
    type_labels = json.dumps(list(stats["type_distribution"].keys()))
    type_values = json.dumps(list(stats["type_distribution"].values()))

    worst_files_rows = ""
    max_count = max([c for _, c in stats["worst_files"]], default=1)
    for file_path, count in stats["worst_files"]:
        pct = int((count / max_count) * 100) if max_count else 0
        worst_files_rows += f"""
        <div class="file-row">
        <div class="file-row-top">
            <span class="file-name">{file_path}</span>
            <span class="file-count">{count}</span>
          </div>
          <div class="file-bar-track"><div class="file-bar-fill" style="width:{pct}%"></div></div>
        </div>"""
    if not worst_files_rows:
        worst_files_rows = '<div class="empty-state">Aucune donnée — lancez votre première analyse.</div>'

    # Selecteur de repo
    current = selected_repo or "all"
    options = f'<option value="all" {"selected" if current == "all" else ""}>Tous les repos</option>'
    for repo in repos:
        sel = "selected" if repo == current else ""
        options += f'<option value="{repo}" {sel}>{repo}</option>'

    # Tableau des PRs analysees
    pr_rows = ""
    for r in pr_list:
        badge_class = risk_badge_class(r.get("risk_level", ""))
        analyzed_date = r.get("analyzed_at", "")[:16].replace("T", " ")
        pr_rows += f"""
        <tr>
          <td>#{r.get('pr_number')}</td>
          <td>{r.get('pr_title', '—')[:50]}</td>
          <td class="repo-tag">{r.get('repo_name', '—')}</td>
          <td><span class="badge {badge_class}">{r.get('score', 0)}/100</span></td>
          <td>{r.get('total_issues', 0)}</td>
          <td class="repo-tag">{analyzed_date}</td>
          <td><a class="view-btn" href="/dashboard/pr/{r.get('pr_number')}?repo={r.get('repo_name', '')}">Voir →</a></td>
        </tr>"""
    if not pr_rows:
        pr_rows = '<tr><td colspan="7"><div class="empty-state">Aucune PR analysée pour le moment.</div></td></tr>'

    body = f"""
  <div class="topbar">
    <div class="brand">
      <div class="brand-mark">AI</div>
      <div class="brand-text">
        <h1>Agent IA de Revue de Code · Smartovate LTD</h1>
      </div>
    </div>
    <div class="header-actions">
      <div class="repo-select">
        <select id="repoSelect">{options}</select>
      </div>
      <a href="https://github.com/apps/agent-revue-code/installations/new" target="_blank" class="theme-toggle" style="text-decoration:none;">
        <span>+ Ajouter un repository</span>
      </a>
      <div class="status-pill">
        <span class="pulse-dot"></span>
        LIVE
      </div>
      <div class="theme-toggle" id="themeToggle" role="button" aria-label="Changer de theme">
        <svg id="themeIcon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></svg>
        <span id="themeLabel">Mode nuit</span>
      </div>
    </div>
  </div>

  <div class="kpi-strip">
    <div class="kpi">
      <div class="kpi-label">PRs Analysées</div>
      <div class="kpi-value accent">{stats['total_prs']}</div>
      <div class="kpi-sub">total surveillé</div>
      <div class="kpi-spark"></div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Score Moyen</div>
      <div class="kpi-value">{stats['average_score']}<span style="font-size:14px;color:var(--text-dim)">/100</span></div>
      <div class="kpi-sub">qualité globale</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Issues Détectées</div>
      <div class="kpi-value warn">{stats['total_issues']}</div>
      <div class="kpi-sub">{stats['critical_count']} critiques</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Fichiers à Risque</div>
      <div class="kpi-value">{len(stats['worst_files'])}</div>
      <div class="kpi-sub">nécessitent attention</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Temps Gagné</div>
      <div class="kpi-value accent">{stats['time_saved']['formatted']}</div>
      <div class="kpi-sub">vs revue manuelle</div>
      <div class="kpi-spark"></div>
    </div>
  </div>

  <div class="grid-2">
    <div class="panel">
      <div class="panel-head"><div class="panel-title">Évolution du score</div></div>
      <div class="chart-wrap"><canvas id="scoreChart"></canvas></div>
    </div>
    <div class="panel">
      <div class="panel-head"><div class="panel-title">Niveaux de risque</div></div>
      <div class="chart-wrap"><canvas id="riskChart"></canvas></div>
    </div>
  </div>

  <div class="grid-3">
    <div class="panel">
      <div class="panel-head"><div class="panel-title">Répartition par type</div></div>
      <div class="chart-wrap" style="height:200px"><canvas id="typeChart"></canvas></div>
    </div>
    <div class="panel">
      <div class="panel-head"><div class="panel-title">Fichiers les plus problématiques</div></div>
      {worst_files_rows}
    </div>
  </div>

  <div class="panel">
    <div class="panel-head"><div class="panel-title">Pull Requests analysées ({len(pr_list)})</div></div>
    <table class="pr-table">
      <tr>
        <th>PR</th><th>Titre</th><th>Repo</th><th>Score</th><th>Issues</th><th>Date</th><th></th>
      </tr>
      {pr_rows}
    </table>
  </div>

<script>
  Chart.defaults.color = '#5e7269';
  Chart.defaults.font.family = "'JetBrains Mono', monospace";
  Chart.defaults.font.size = 11;

  new Chart(document.getElementById('scoreChart'), {{
    type: 'line',
    data: {{
      labels: {score_labels},
      datasets: [{{
        label: 'Score',
        data: {score_values},
        borderColor: '#3da9ff',
        backgroundColor: 'rgba(61,169,255,0.08)',
        pointBackgroundColor: '#06090c',
        pointBorderColor: '#3da9ff',
        pointBorderWidth: 2,
        pointRadius: 4,
        pointHoverRadius: 6,
        tension: 0.35,
        fill: true,
        borderWidth: 2
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        y: {{ min: 0, max: 100, grid: {{ color: '#182026' }}, border: {{ display: false }} }},
        x: {{ grid: {{ display: false }}, border: {{ display: false }} }}
      }}
    }}
  }});

  new Chart(document.getElementById('riskChart'), {{
    type: 'doughnut',
    data: {{
      labels: {risk_labels},
      datasets: [{{
        data: {risk_values},
        backgroundColor: ['#ff5c5c', '#ff8a3d', '#ffb454', '#3da9ff', '#2d7dff'],
        borderColor: '#06090c',
        borderWidth: 3
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      cutout: '68%',
      plugins: {{ legend: {{ position: 'bottom', labels: {{ boxWidth: 10, padding: 14 }} }} }}
    }}
  }});

  new Chart(document.getElementById('typeChart'), {{
    type: 'bar',
    data: {{
      labels: {type_labels},
      datasets: [{{
        data: {type_values},
        backgroundColor: '#2d7dff',
        borderRadius: 4,
        maxBarThickness: 36
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        y: {{ grid: {{ color: '#182026' }}, border: {{ display: false }} }},
        x: {{ grid: {{ display: false }}, border: {{ display: false }} }}
      }}
    }}
  }});

  setTimeout(() => location.reload(), 30000);
</script>
"""

    return render_page_shell("Agent IA de Revue de Code — Dashboard", body)


def generate_pr_detail_html(report: dict) -> str:
    """
    Genere la page de detail complete pour une PR specifique
    """
    if not report:
        body = """
  <div class="topbar">
    <div class="brand">
      <div class="brand-mark">AI</div>
      <div class="brand-text"><h1>PR introuvable</h1></div>
    </div>
  </div>
  <div class="panel"><div class="empty-state">Aucun rapport trouvé pour cette PR.</div></div>
  <a class="back-link" href="/dashboard">← Retour au dashboard</a>
"""
        return render_page_shell("PR introuvable", body)

    badge_class = risk_badge_class(report.get("risk_level", ""))
    analyzed_date = report.get("analyzed_at", "")[:19].replace("T", " ")

    file_rows = ""
    for file_path, metrics in report.get("file_metrics", {}).items():
        file_rows += f"""
        <tr>
          <td>{file_path}</td>
          <td>{metrics.get('total_issues', 0)}</td>
          <td>{metrics.get('critical', 0)}</td>
          <td>{metrics.get('high', 0)}</td>
          <td>{metrics.get('medium', 0)}</td>
          <td>{metrics.get('low', 0)}</td>
        </tr>"""
    if not file_rows:
        file_rows = '<tr><td colspan="6"><div class="empty-state">Aucun fichier concerné.</div></td></tr>'

    issue_cards = ""
    for issue in report.get("issues", []):
        severity = issue.get("severity", "low")
        issue_cards += f"""
        <div class="issue-card {severity}">
          <div class="issue-head">
            <span class="badge {severity}">{severity.upper()}</span>
            <span class="issue-loc">{issue.get('file_path', '')} · ligne {issue.get('line', '?')}</span>
          </div>
          <div class="issue-desc">{issue.get('description', '')}</div>
          <div class="issue-fix"><b>Suggestion :</b> {issue.get('suggestion', 'N/A')}</div>
        </div>"""
    if not issue_cards:
        issue_cards = (
            '<div class="empty-state">Aucun problème détecté sur cette PR. ✅</div>'
        )

    body = f"""
  <div class="topbar">
    <div class="brand">
      <div class="brand-mark">AI</div>
      <div class="brand-text">
        <h1>PR #{report.get('pr_number')} — {report.get('pr_title', '')[:60]}</h1>
      </div>
    </div>
    <div class="header-actions">
      <div class="theme-toggle" id="themeToggle" role="button" aria-label="Changer de theme">
        <svg id="themeIcon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></svg>
        <span id="themeLabel">Mode nuit</span>
      </div>
    </div>
  </div>

  <a class="back-link" href="/dashboard">← Retour au dashboard</a>

  <div class="kpi-strip" style="grid-template-columns: repeat(5, 1fr); margin-top: 16px;">
    <div class="kpi">
      <div class="kpi-label">Score</div>
      <div class="kpi-value accent">{report.get('score', 0)}<span style="font-size:14px;color:var(--text-dim)">/100</span></div>
      <div class="kpi-sub"><span class="badge {badge_class}">{report.get('risk_level', 'N/A')}</span></div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Repository</div>
      <div class="kpi-value" style="font-size:16px;">{report.get('repo_name', '—')}</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Issues totales</div>
      <div class="kpi-value warn">{report.get('total_issues', 0)}</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Temps Gagné</div>
      <div class="kpi-value accent">{calculate_time_saved([report])['formatted']}</div>
      <div class="kpi-sub">vs revue manuelle</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Analysée le</div>
      <div class="kpi-value" style="font-size:14px;">{analyzed_date}</div>
    </div>
  </div>

  <div class="panel">
    <div class="panel-head"><div class="panel-title">Métriques par fichier</div></div>
    <table class="pr-table">
      <tr><th>Fichier</th><th>Total</th><th>Critical</th><th>High</th><th>Medium</th><th>Low</th></tr>
      {file_rows}
    </table>
  </div>

  <div class="panel">
    <div class="panel-head"><div class="panel-title">Problèmes détectés ({report.get('total_issues', 0)})</div></div>
    {issue_cards}
  </div>
"""

    return render_page_shell(f"PR #{report.get('pr_number')} — Détail", body)
