# README para TI / Implantação Biasi

## Stack

- Backend: FastAPI + Python 3.11
- Frontend: HTML/CSS/JS servido pelo FastAPI
- Deploy: Docker
- Porta: usar variável `PORT`; padrão 8000
- Healthcheck: `/health`

## Variáveis obrigatórias

```env
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5.2
OPENAI_REASONING_EFFORT=high
USE_MOCK_AGENTS=false
HOSTED_MODE=true
CORS_ORIGINS=*
```

## Comando de execução

```bash
uvicorn app.main:app --app-dir /app/backend --host 0.0.0.0 --port ${PORT:-8000}
```

## Docker local

```bash
docker build -t orquestra-biasi-histograma .
docker run -p 8000:8000 --env-file .env.example orquestra-biasi-histograma
```

## Observações

- PDFs grandes podem levar tempo para extração.
- Para ambiente público, recomenda-se adicionar autenticação Microsoft Entra ID.
- Para ambiente interno, restringir acesso por rede/VPN ou autenticação.
- Não expor `OPENAI_API_KEY` no frontend.
```
