# Script base para publicar no Azure Container Apps.
# Deve ser executado por alguém logado no Azure CLI com permissões no tenant da Biasi.

param(
  [string]$ResourceGroup = "rg-orquestra-biasi",
  [string]$Location = "brazilsouth",
  [string]$AppName = "orquestra-biasi-histograma",
  [string]$EnvName = "env-orquestra-biasi",
  [string]$ImageName = "orquestra-biasi-histograma:latest"
)

Write-Host "Este script é um modelo. Ajuste registry/imagem conforme padrão da Biasi." -ForegroundColor Yellow
Write-Host "Recomendação: publicar via GitHub Actions ou Azure Container Registry." -ForegroundColor Yellow

# Exemplo de criação de Resource Group e ambiente
az group create --name $ResourceGroup --location $Location
az containerapp env create --name $EnvName --resource-group $ResourceGroup --location $Location

# A imagem precisa estar em um registry acessível pelo Azure.
# Depois, criar o container app com variáveis de ambiente.
# az containerapp create `
#   --name $AppName `
#   --resource-group $ResourceGroup `
#   --environment $EnvName `
#   --image <seu-registry>/<sua-imagem>:latest `
#   --target-port 8000 `
#   --ingress external `
#   --env-vars OPENAI_MODEL=gpt-5.2 OPENAI_REASONING_EFFORT=high USE_MOCK_AGENTS=false HOSTED_MODE=true CORS_ORIGINS=* OPENAI_API_KEY=secretref:openai-api-key
