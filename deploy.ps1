# ============================================================
# Script de déploiement automatique — Agent IA de Revue de Code
# Smartovate LTD — Stage Été 2026
# Usage : .\deploy.ps1
# ============================================================

param(
    [string]$Target = "all",  # all, azure, lambda
    [string]$Message = "update: deploiement automatique"
)

Write-Host "🚀 Déploiement de l'Agent IA de Revue de Code" -ForegroundColor Blue
Write-Host "============================================================" -ForegroundColor Blue

# ── ÉTAPE 1 : Git commit et push ──
Write-Host "`n1️⃣ Git commit et push..." -ForegroundColor Yellow
git add .
git commit -m $Message
git push origin main
Write-Host "✅ Code poussé sur GitHub" -ForegroundColor Green

# ── ÉTAPE 2 : Déploiement Azure ──
if ($Target -eq "all" -or $Target -eq "azure") {
    Write-Host "`n2️⃣ Déploiement sur Azure Container Apps..." -ForegroundColor Yellow

    Write-Host "   Construction de l'image Docker..."
    docker build -t agent-revue-code .

    Write-Host "   Tag de l'image..."
    docker tag agent-revue-code agentrevuecode.azurecr.io/agent-revue-code:latest

    Write-Host "   Connexion au registry Azure..."
    az acr login --name agentrevuecode

    Write-Host "   Push de l'image..."
    docker push agentrevuecode.azurecr.io/agent-revue-code:latest

    Write-Host "   Mise à jour Azure Container Apps..."
    az containerapp update --name agent-revue-app --resource-group mohamedbadishajji --image agentrevuecode.azurecr.io/agent-revue-code:latest

    Write-Host "✅ Azure déployé avec succès !" -ForegroundColor Green
}

# ── ÉTAPE 3 : Déploiement AWS Lambda ──
if ($Target -eq "all" -or $Target -eq "lambda") {
    Write-Host "`n3️⃣ Déploiement sur AWS Lambda..." -ForegroundColor Yellow

    Write-Host "   Nettoyage du package précédent..."
    if (Test-Path package) { Remove-Item -Recurse -Force package }
    if (Test-Path lambda_package.zip) { Remove-Item -Force lambda_package.zip }

    Write-Host "   Installation des dépendances..."
    pip install -r requirements.txt --target ./package --quiet

    Write-Host "   Copie du code..."
    Copy-Item -Recurse app package/app
    Copy-Item lambda_handler.py package/lambda_handler.py

    Write-Host "   Création du ZIP..."
    Compress-Archive -Path package/* -DestinationPath lambda_package.zip -Force

    Write-Host "   Upload sur S3..."
    aws s3 cp lambda_package.zip s3://agent-revue-code-deploy/lambda_package.zip --region eu-north-1

    Write-Host "   Mise à jour Lambda..."
    aws lambda update-function-code --function-name agent-revue-code --s3-bucket agent-revue-code-deploy --s3-key lambda_package.zip --region eu-north-1

    Write-Host "✅ AWS Lambda déployé avec succès !" -ForegroundColor Green
}

Write-Host "`n🎉 Déploiement terminé !" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Blue
Write-Host "Azure  : [voir .env AZURE_WEBHOOK_URL]"
Write-Host "Lambda : [voir .env LAMBDA_WEBHOOK_URL]"
#.\deploy.ps1 -Message "feat: nouvelle fonctionnalité"--->Déployer sur les deux plateformes 
#.\deploy.ps1 -Target azure -Message "fix: correction bug"--->Déployer uniquement sur Azure
