import os
import json
import glob
from datetime import datetime
from collections import defaultdict

REPORTS_DIR = "reports"
ESTIMATED_TIME_PER_REVIEW_MINUTES = 15


def get_all_reports() -> list:
    if not os.path.exists(REPORTS_DIR):
        return []
    reports = []
    pattern = os.path.join(REPORTS_DIR, "*.json")
    for filepath in glob.glob(pattern):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                reports.append(json.load(f))
        except Exception as e:
            print(f"   Erreur lecture {filepath} : {str(e)}")
    return reports


def calculate_time_saved(total_prs: int) -> dict:
    total_minutes = total_prs * ESTIMATED_TIME_PER_REVIEW_MINUTES
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return {
        "total_minutes": total_minutes,
        "hours": hours,
        "minutes": minutes,
        "formatted": f"{hours}h {minutes}min" if hours > 0 else f"{minutes}min"
    }


def calculate_dashboard_stats(reports: list) -> dict:
    if not reports:
        return {
            "total_prs": 0, "average_score": 0, "total_issues": 0,
            "score_distribution": {}, "type_distribution": {},
            "worst_files": [], "score_history": [],
            "time_saved": calculate_time_saved(0),
            "critical_count": 0, "approved_count": 0
        }

    total_prs = len(reports)
    total_score = sum(r.get("score", 0) for r in reports)
    average_score = round(total_score / total_prs, 1)
    total_issues = sum(r.get("total_issues", 0) for r in reports)

    score_distribution = defaultdict(int)
    for r in reports:
        score_distribution[r.get("risk_level", "UNKNOWN")] += 1

    type_distribution = defaultdict(int)
    for r in reports:
        for issue_type, count in r.get("type_metrics", {}).items():
            type_distribution[issue_type] += count

    file_issue_count = defaultdict(int)
    for r in reports:
        for file_path, metrics in r.get("file_metrics", {}).items():
            file_issue_count[file_path] += metrics.get("total_issues", 0)

    worst_files = sorted(file_issue_count.items(), key=lambda x: x[1], reverse=True)[:5]

    score_history = sorted(
        [{"pr_number": r.get("pr_number"), "score": r.get("score"), "date": r.get("analyzed_at", "")}
         for r in reports],
        key=lambda x: x["date"]
    )

    time_saved = calculate_time_saved(total_prs)
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
        "approved_count": approved_count
    }


def generate_dashboard_html(stats: dict) -> str:
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

    now_str = datetime.now().strftime("%H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agent IA de Revue de Code — Smartovate LTD</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
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
  .topbar, .kpi-strip, .grid-2, .grid-3, footer {{
    position: relative;
    z-index: 1;
  }}

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
    display: flex; align-items: center; gap: 10px;
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
  .theme-toggle {{
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

  footer {{
    margin-top: 24px; text-align: center; font-family: var(--mono);
    font-size: 10.5px; color: var(--text-dim); letter-spacing: 0.04em;
  }}

  @media (max-width: 900px) {{
    .kpi-strip {{ grid-template-columns: repeat(2, 1fr); }}
    .grid-2, .grid-3 {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
<canvas id="bg-canvas"></canvas>

  <div class="topbar">
    <div class="brand">
      <div class="brand-mark">AI</div>
      <div class="brand-text">
        <h1>Agent IA de Revue de Code · Smartovate LTD</h1>
      </div>
    </div>
    <div class="header-actions">
      <div class="status-pill">
        <span class="pulse-dot"></span>
        LIVE · {now_str}
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


<script>
  // ── Theme toggle (dark / light) ──
  const ICONS = {{
    dark: '<circle cx="12" cy="12" r="4"></circle><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
    light: '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>'
  }};
  function applyTheme(theme) {{
    document.documentElement.setAttribute('data-theme', theme);
    document.getElementById('themeIcon').innerHTML = theme === 'dark' ? ICONS.light : ICONS.dark;
    document.getElementById('themeLabel').textContent = theme === 'dark' ? 'Mode jour' : 'Mode nuit';
    localStorage.setItem('dashboard-theme', theme);
  }}
  const savedTheme = localStorage.getItem('dashboard-theme') || 'dark';
  applyTheme(savedTheme);
  document.getElementById('themeToggle').addEventListener('click', () => {{
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    applyTheme(current === 'dark' ? 'light' : 'dark');
  }});

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

  // Auto-refresh toutes les 30 secondes pour un effet "live"
  setTimeout(() => location.reload(), 30000);
</script>
</body>
</html>"""

    return html