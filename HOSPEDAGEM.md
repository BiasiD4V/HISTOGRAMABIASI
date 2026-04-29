# Hospedagem do Orquestra Biasi

## Recomendacao

Para uso interno da Biasi, a recomendacao principal continua sendo Azure Container Apps ou Azure App Service.

Se a prioridade for colocar no ar rapido, este pacote agora tambem esta pronto para Vercel.

## O que muda em ambiente hospedado

- O app deixa de rodar apenas em `localhost`.
- A equipe passa a acessar uma URL fixa.
- A chave OpenAI fica nas variaveis de ambiente do provedor.
- O frontend nao salva a chave pelo navegador quando `HOSTED_MODE=true`.

## Variaveis de ambiente

Configure no provedor:

- `OPENAI_API_KEY`
- `OPENAI_MODEL=gpt-5.2`
- `OPENAI_REASONING_EFFORT=high`
- `USE_MOCK_AGENTS=false`
- `HOSTED_MODE=true`
- `CORS_ORIGINS=*`

## Opcao A: Azure Container Apps

Essa continua sendo a opcao mais alinhada ao ambiente corporativo da Biasi.

1. Instalar Azure CLI.
2. Abrir PowerShell dentro da pasta do app.
3. Rodar:

```powershell
.\azure-container-app-deploy.ps1
```

## Opcao B: Render/Railway

Tambem funciona com o `Dockerfile` incluido.

No Render:

1. Criar novo Web Service.
2. Conectar o repositorio Git.
3. Selecionar ambiente Docker.
4. Cadastrar as variaveis de ambiente.
5. Deploy.

## Opcao C: Vercel

Esta versao foi ajustada para Vercel sem Docker.

Arquivos usados nessa rota:

- `app.py`
- `requirements.txt`
- `vercel.json`
- `.vercelignore`

Fluxo:

1. Abrir terminal na pasta do app.
2. Rodar `vercel login` se necessario.
3. Rodar `vercel`.
4. Rodar `vercel --prod` para publicar em producao.

Observacao importante: a Vercel usa Functions, nao containers. Para anexos muito grandes, Azure ou Render tendem a ser mais robustos.

## Opcao D: Azure App Service

Tambem e possivel hospedar em Azure App Service com Python/FastAPI.

Startup command sugerido:

```bash
uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

## Proximo passo ideal

Subir essa pasta para um repositorio privado da Biasi e configurar deploy automatico no provedor escolhido.
