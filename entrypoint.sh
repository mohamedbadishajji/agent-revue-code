#!/bin/bash
set -e

echo " Démarrage de l'Agent IA de Revue de Code — Smartovate LTD"
echo "=============================================================="

# Configurer les variables d'environnement depuis les inputs GitHub Actions
export GITHUB_APP_ID=$INPUT_GITHUB_APP_ID
export GITHUB_INSTALLATION_ID=$INPUT_GITHUB_INSTALLATION_ID
export GITHUB_WEBHOOK_SECRET=$INPUT_GITHUB_WEBHOOK_SECRET
export AWS_ACCESS_KEY_ID=$INPUT_AWS_ACCESS_KEY_ID
export AWS_SECRET_ACCESS_KEY=$INPUT_AWS_SECRET_ACCESS_KEY
export AWS_REGION=${INPUT_AWS_REGION:-eu-north-1}
export AWS_BEDROCK_MODEL_ID=${INPUT_AWS_BEDROCK_MODEL_ID:-eu.anthropic.claude-sonnet-4-6}
export INCLUDE_TESTS=${INPUT_INCLUDE_TESTS:-false}

# Écrire la clé privée dans un fichier temporaire
echo "$INPUT_GITHUB_PRIVATE_KEY" > /tmp/private_key.pem
export GITHUB_PRIVATE_KEY_PATH=/tmp/private_key.pem

# Récupérer les infos de la PR depuis le contexte GitHub Actions
REPO_NAME=$GITHUB_REPOSITORY
PR_NUMBER=${{ github.event.pull_request.number }}
PR_TITLE=${{ github.event.pull_request.title }}

echo " Repo : $REPO_NAME"
echo " PR : #$PR_NUMBER — $PR_TITLE"

# Lancer l'analyse
python entrypoint.py \
    --repo "$REPO_NAME" \
    --pr "$PR_NUMBER" \
    --title "$PR_TITLE" \
    --include-tests "$INCLUDE_TESTS"

echo "✅ Analyse terminée !"