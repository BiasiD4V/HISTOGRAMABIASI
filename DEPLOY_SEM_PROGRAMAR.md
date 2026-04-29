# Orquestra Biasi - hospedagem sem rodar localhost

## O que este pacote resolve

Este pacote transforma o app do Histograma em uma aplicação hospedável em nuvem.
Depois de hospedado, você acessa uma URL fixa, por exemplo:

https://orquestra-biasi-histograma.onrender.com

ou

https://orquestra-biasi-histograma.azurecontainerapps.io

## O que eu NÃO consigo fazer sem acesso

Para publicar de verdade eu preciso de acesso a uma destas contas da Biasi:

- GitHub/GitLab/Bitbucket onde o código será salvo;
- Render ou Azure para criar o serviço;
- permissão para configurar variáveis de ambiente, principalmente OPENAI_API_KEY.

Sem esses acessos, o pacote fica pronto para hospedagem, mas eu não consigo clicar em "deploy" no ambiente de vocês.

## Caminho mais simples: Render

1. Criar um repositório privado no GitHub chamado `orquestra-biasi-histograma`.
2. Subir todo este pacote para o repositório.
3. Acessar Render > New > Web Service.
4. Conectar o repositório.
5. Render deve detectar o `Dockerfile`.
6. Configurar estas variáveis de ambiente:

OPENAI_API_KEY=sua_chave_nova
OPENAI_MODEL=gpt-5.2
OPENAI_REASONING_EFFORT=high
USE_MOCK_AGENTS=false
HOSTED_MODE=true
CORS_ORIGINS=*

7. Clicar em Deploy.

A cada atualização no GitHub, o Render publica uma nova versão automaticamente.

## Caminho recomendado para a Biasi: Azure Container Apps

1. Criar um Azure Container App.
2. Usar este Dockerfile.
3. Configurar as mesmas variáveis de ambiente.
4. Ativar domínio fixo.
5. Futuramente conectar Microsoft Entra ID e SharePoint.

## Segurança da chave OpenAI

Em hospedagem, não cole a chave no navegador.
A chave deve ficar no servidor como variável de ambiente:

OPENAI_API_KEY

O app agora tem `HOSTED_MODE=true`, então a tela de configuração não grava chave pelo navegador.

## Atualização futura

Fluxo ideal:

ChatGPT ajusta o pacote -> alguém sobe no GitHub -> deploy automático -> todos usam a mesma URL.

