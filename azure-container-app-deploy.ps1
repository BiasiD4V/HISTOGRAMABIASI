# Deploy simples no Azure Container Apps
# Requisitos: Azure CLI instalado e permissao para criar recursos no Azure.
# Execute este arquivo no PowerShell dentro da pasta do app.

$ErrorActionPreference = "Stop"

$RESOURCE_GROUP = "rg-orquestra-biasi"
$APP_NAME = "orquestra-biasi-histograma"
$LOCATION = "brazilsouth"
$MODEL = "gpt-5.2"

Write-Host "Entrando no Azure..."
az login

$OPENAI_API_KEY = Read-Host "Cole sua OPENAI_API_KEY" -AsSecureString
$OPENAI_API_KEY_PLAIN = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($OPENAI_API_KEY))

Write-Host "Criando grupo de recursos..."
az group create --name $RESOURCE_GROUP --location $LOCATION

Write-Host "Publicando Container App. Pode demorar alguns minutos..."
az containerapp up `
  --name $APP_NAME `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION `
  --source . `
  --ingress external `
  --target-port 8000 `
  --env-vars OPENAI_API_KEY=$OPENAI_API_KEY_PLAIN OPENAI_MODEL=$MODEL OPENAI_REASONING_EFFORT=high USE_MOCK_AGENTS=false CORS_ORIGINS="*"

Write-Host "URL do app:"
az containerapp show --name $APP_NAME --resource-group $RESOURCE_GROUP --query properties.configuration.ingress.fqdn -o tsv
