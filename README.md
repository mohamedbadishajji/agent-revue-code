#  Agent IA de Revue de Code

Agent intelligent d'automatisation de la revue de code pour GitHub, s'appuyant sur un modèle de langage (Claude Sonnet via AWS Bedrock) pour analyser automatiquement les Pull Requests, détecter les vulnérabilités et problèmes de qualité, et publier des retours structurés — sans aucune intervention manuelle.

Projet développé dans le cadre d'un stage d'été 2026 chez **Smartovate LTD**.

---

##  Sommaire

- [Fonctionnalités](#-fonctionnalités)
- [Architecture](#-architecture)
- [Stack technique](#-stack-technique)
- [Installation locale](#-installation-locale)
- [Variables d'environnement](#-variables-denvironnement)
- [Déploiement](#-déploiement)
- [Structure du projet](#-structure-du-projet)
- [Utilisation](#-utilisation)
- [Limitations connues](#-limitations-connues)
- [Auteur](#-auteur)

---

##  Fonctionnalités

### Analyse automatique
- Détection automatique des Pull Requests via webhook GitHub
- Analyse du code par intelligence artificielle (AWS Bedrock — Claude Sonnet)
- Support de **tous les langages de programmation**, avec règles spécifiques renforcées pour 12 langages majeurs (Python, JavaScript, TypeScript, Java, Go, PHP, Ruby, C#, Swift, Kotlin, C, C++)
- Détection des vulnérabilités de sécurité (couverture OWASP Top 10)
- Système de scoring de sévérité (0-100) avec niveaux de risque qualitatifs
- Validation anti-hallucination des résultats produits par le modèle

### Publication automatique
- Commentaires inline positionnés précisément sur les lignes concernées
- Suggestions de correction applicables en un clic (GitHub Suggestions)
- Résumé global avec tableau de sévérité
- Labels colorés automatiques selon la criticité
- Décision d'approbation / demande de modification selon un seuil configurable

### Robustesse
- Gestion des Pull Requests volumineuses (priorisation des fichiers les plus impactés)
- Retry automatique avec backoff progressif en cas d'échec transitoire
- Déduplication des commentaires lors de ré-analyses successives
- Configuration personnalisable par dépôt (`.revue-config.yml`)

### Dashboard & comptes utilisateurs
- Tableau de bord de métriques (score moyen, PRs analysées, temps gagné estimé)
- Historique persistant des analyses (Azure Blob Storage)
- Système de comptes utilisateurs individuels (inscription, connexion, réinitialisation de mot de passe par email)
- Filtrage du dashboard par utilisateur, selon les dépôts associés à son compte
- Page de paramètres du compte (nom d'utilisateur, email, mot de passe, profil GitHub)

---

##  Architecture

```
GitHub (Pull Request)
        │
        ▼
   Webhook (signature HMAC vérifiée)
        │
        ▼
┌───────────────────────────┐
│  Azure Container Apps      │
│  (FastAPI + BackgroundTasks)│
└─────────┬───────────────────┘
          │
          ├──► AWS Bedrock (analyse LLM)
          ├──► Azure Blob Storage (rapports)
          ├──► Azure SQL Database (comptes utilisateurs)
          ├──► Azure Communication Services (emails)
          │
          ▼
   Publication sur GitHub
   (commentaires, labels, review)
```

Une infrastructure serverless alternative est également disponible sur **AWS Lambda**, à titre démonstratif.

---

##  Stack technique

| Composant | Technologie |
|-----------|-------------|
| Langage | Python 3.11 |
| Framework web | FastAPI |
| Modèle IA | AWS Bedrock — Claude Sonnet 4.6 |
| Hébergement principal | Azure Container Apps |
| Infrastructure secondaire | AWS Lambda |
| Stockage des rapports | Azure Blob Storage |
| Base de données utilisateurs | Azure SQL Database |
| Envoi d'emails | Azure Communication Services |
| Intégration GitHub | GitHub App + API REST |
| Authentification | JWT + bcrypt |
| Conteneurisation | Docker |
| CI/CD | GitHub Actions |

---

##  Installation locale

### Prérequis
- Python 3.11+
- Docker Desktop
- Un compte GitHub avec une GitHub App configurée
- Un compte AWS avec accès à Bedrock
- Un compte Azure (Container Apps, Blob Storage, SQL Database, Communication Services)

### Étapes

```bash
# 1. Cloner le dépôt
git clone https://github.com/mohamedbadishajji/agent-revue-code.git
cd agent-revue-code

# 2. Créer un environnement virtuel (recommandé)
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # macOS/Linux

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer les variables d'environnement
# Copier .env.example vers .env et renseigner les valeurs (voir section ci-dessous)

# 5. Lancer le serveur en local
uvicorn app.main:app --reload --port 8000
```

Le dashboard est alors accessible sur `http://127.0.0.1:8000/dashboard`.

### Lancer avec Docker

```bash
docker build -t agent-revue-code .
docker run -p 8000:8000 --env-file .env agent-revue-code
```

---

##  Variables d'environnement

Créer un fichier `.env` à la racine du projet avec les variables suivantes :

```env
# GitHub App
GITHUB_APP_ID=
GITHUB_INSTALLATION_ID=
GITHUB_WEBHOOK_SECRET=
GITHUB_PRIVATE_KEY_PATH=chemin/vers/cle-privee.pem
# ou, pour la production (recommandé) :
GITHUB_PRIVATE_KEY_BASE64=

# OAuth GitHub (optionnel)
GITHUB_OAUTH_CLIENT_ID=
GITHUB_OAUTH_CLIENT_SECRET=

# AWS Bedrock
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=eu-north-1
AWS_BEDROCK_MODEL_ID=arn:aws:bedrock:eu-north-1:XXXXXXXXXXXX:inference-profile/eu.anthropic.claude-sonnet-4-6

# Azure Blob Storage
AZURE_STORAGE_ACCOUNT_NAME=
AZURE_STORAGE_ACCOUNT_KEY=
AZURE_STORAGE_CONTAINER_NAME=reports

# Azure SQL Database
AZURE_SQL_SERVER=
AZURE_SQL_DATABASE=
AZURE_SQL_USERNAME=
AZURE_SQL_PASSWORD=

# Azure Communication Services (emails)
AZURE_COMMUNICATION_CONNECTION_STRING=
AZURE_COMMUNICATION_SENDER_EMAIL=

# Sécurité des sessions
JWT_SECRET_KEY=
```

> ⚠️ Ne jamais committer le fichier `.env` ni les clés privées (`.pem`). Vérifier que `.gitignore` les exclut bien.

---

##  Déploiement

### Azure Container Apps

```powershell
docker build -t agent-revue-code .
docker tag agent-revue-code <votre-registry>.azurecr.io/agent-revue-code:latest
az acr login --name <votre-registry>
docker push <votre-registry>.azurecr.io/agent-revue-code:latest
az containerapp update --name <nom-app> --resource-group <resource-group> --revision-suffix v<timestamp>
```

> Le pilote ODBC pour SQL Server sous Linux est installé automatiquement via le `Dockerfile`.

### AWS Lambda (infrastructure alternative)

```powershell
pip install -r requirements.txt --target ./package
Copy-Item -Recurse app package/app
Copy-Item lambda_handler.py package/lambda_handler.py
Compress-Archive -Path package/* -DestinationPath lambda_package.zip -Force
aws s3 cp lambda_package.zip s3://<votre-bucket>/lambda_package.zip
aws lambda update-function-code --function-name <nom-fonction> --s3-bucket <votre-bucket> --s3-key lambda_package.zip
```

> ⚠️ Pour toute dépendance contenant du code compilé natif (ex. `pyodbc`), construire le package dans un environnement Linux (via Docker) pour garantir la compatibilité avec l'environnement d'exécution Lambda.

Un script d'automatisation complet (`deploy.ps1`) est disponible à la racine du projet pour déployer indifféremment vers Azure, AWS, ou les deux.

---

##  Structure du projet

```
agent-revue-code/
├── app/
│   ├── main.py              # Serveur FastAPI, routes webhook/dashboard/auth
│   ├── analyzer.py          # Orchestration de l'analyse d'une PR
│   ├── github_client.py     # Authentification et client GitHub App
│   ├── diff_parser.py       # Extraction et parsing du diff
│   ├── filters.py           # Filtrage des fichiers pertinents
│   ├── prompt.py            # Prompt engineering (règles par langage)
│   ├── llm_client.py        # Client AWS Bedrock
│   ├── validator.py         # Validation anti-hallucination
│   ├── scoring.py           # Calcul du score de sévérité
│   ├── review_comment.py    # Publication des commentaires GitHub
│   ├── pr_labeler.py        # Application des labels
│   ├── pr_approval.py       # Décision d'approbation
│   ├── rate_limiter.py      # Gestion du rate limiting + retry
│   ├── duplicate_checker.py # Déduplication des commentaires
│   ├── quality_report.py    # Génération des rapports JSON/Markdown
│   ├── config_loader.py     # Lecture de .revue-config.yml
│   ├── dashboard.py         # Génération du dashboard HTML
│   ├── database.py          # Modèles SQLAlchemy (utilisateurs, repos)
│   └── auth_utils.py        # Hashing, JWT, réinitialisation de mot de passe
├── tests/                   # Tests unitaires (Pytest)
├── .github/workflows/       # Pipeline CI/CD (GitHub Actions)
├── Dockerfile
├── requirements.txt
├── deploy.ps1                # Script de déploiement automatisé
├── lambda_handler.py         # Point d'entrée AWS Lambda
└── README.md
```

---

##  Utilisation

### Configuration par dépôt

Chaque dépôt peut définir un fichier `.revue-config.yml` à sa racine pour personnaliser le comportement de l'agent :

```yaml
severity_threshold: high        # low | medium | high | critical
include_tests: false
ignored_paths:
  - "migrations/"
  - "vendor/"
max_file_size_kb: 1000
languages_enabled: []            # vide = tous les langages acceptés
custom_instructions: |
  Instructions spécifiques à ce projet, injectées dans le prompt.
```

En l'absence de ce fichier, une configuration par défaut raisonnable est appliquée.

### Installation de l'agent sur un nouveau dépôt

1. Depuis le dashboard, cliquer sur **"+ Ajouter un repository"**
2. Sélectionner le(s) dépôt(s) souhaité(s) sur l'interface GitHub native
3. Toute Pull Request future sur ce dépôt sera automatiquement analysée

### Créer un compte et suivre ses propres dépôts

1. S'inscrire via `/auth/register`
2. Depuis le dashboard, aller sur **"📁 Mes repositories"**
3. Déclarer le nom complet d'un dépôt (`owner/repo`) — une vérification technique confirme l'accès avant association
4. Le dashboard affiche désormais uniquement les statistiques de ce(s) dépôt(s)

---

## ⚠️ Limitations connues

- Un dépôt ne peut être associé qu'à un seul compte utilisateur à la fois
- L'infrastructure AWS Lambda n'est pas synchronisée avec les fonctionnalités liées aux comptes utilisateurs (problème de compatibilité binaire de certaines dépendances, documenté)
- Le dashboard reste consultable sans authentification (vue globale non filtrée) — un choix de conception assumé plutôt qu'un oubli

---

##  Auteur

**Mohamed Badis Hajji**
Stage d'été 2026 — Smartovate LTD
École Nationale d'Ingénieurs de Carthage — Filière Génie Informatique

Encadrant professionnel : Abdelkhalek Bakkari (CEO & Founder, Smartovate LTD)
