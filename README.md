ORQUESTRA BIASI - APP PRONTO PARA USO

WINDOWS
1. Extraia o ZIP.
2. Dê dois cliques em INICIAR_APP_WINDOWS.bat.
3. Aguarde o navegador abrir.
4. No bloco "00 · Configuração sem código", cole sua chave OpenAI e clique em Salvar configuração.
5. Anexe os arquivos do projeto e clique em Rodar agentes reais.

MAC
1. Extraia o ZIP.
2. Dê dois cliques em INICIAR_APP_MAC.command.
3. Se o Mac bloquear, clique com botão direito > Abrir.

OBSERVAÇÕES
- Você não precisa programar.
- A primeira abertura pode demorar porque instala as dependências.
- Para testar sem API, escolha "Demonstração" no bloco de configuração.
- Para agentes reais, escolha "Agentes reais" e cole sua chave OpenAI.
- Sua chave fica salva apenas localmente no arquivo .env dentro da pasta do app.

---

## Versao hospedavel

Esta versao inclui arquivos para hospedagem em nuvem:

- `Dockerfile`
- `.dockerignore`
- `azure-container-app-deploy.ps1`
- `render.yaml`
- `.github/workflows/deploy-azure-container-apps.yml`
- `HOSPEDAGEM.md`

Para a Biasi, o caminho recomendado e hospedar no Azure Container Apps ou Azure App Service, mantendo a chave OpenAI como variavel de ambiente do servidor.
