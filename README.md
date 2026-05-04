# Assistente de Chamados TI On-Premise

Base inicial de um bot corporativo on-premise para triagem, abertura, consulta e complemento simulado de chamados de TI.

## Objetivo

Este MVP cria a fundacao modular do "Assistente de Chamados TI On-Premise" usando Python, FastAPI e um simulador web em HTML/CSS/JavaScript puro. O foco e validar o motor unico de conversa, sem integracoes reais externas.

## Escopo do MVP

- Autenticacao simulada do usuario Pedro Torres.
- Motor de conversa orientado por estados.
- Abertura de chamado rapido e detalhado.
- Categoria "Outro" com aproximacao inteligente simulada e confirmacao.
- Organizacao minima do texto do usuario com IA local ultra leve para portugues.
- Mapeamento de impacto para gravidade.
- Resumo antes da criacao do chamado.
- Criacao, consulta e complemento de chamados simulados em memoria.
- Protecoes basicas contra abuso, SQL digitado, comandos e texto excessivo.
- Pasta reservada e isolada para futura integracao GLPI.

## Ainda nao implementado

Nao ha GLPI real, Telegram real, WhatsApp real, Microsoft Teams real, banco de dados real, LDAP/AD, IA externa, upload de anexos ou envio de mensagens externas.

## Instalar

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

No PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

O `requirements.txt` instala apenas as dependencias Python da aplicacao. A IA generativa local roda em um runtime on-premise separado, via Ollama, usando por padrao o modelo `hf.co/Qwen/Qwen3-0.6B-GGUF:Q8_0`.

## Rodar

```bash
uvicorn app.main:app --reload
```

Depois acesse:

[http://localhost:8000](http://localhost:8000)

## Testes

```bash
pytest
```

## Estrutura

```text
app/
  api_http_routes/                 Rotas FastAPI
  application_config/              Configuracao e logs
  authentication_and_identity/      Autenticacao simulada e identidade
  channel_adapters/                 Adaptadores de canal
  conversation_engine/              Motor unico de conversa
  glpi_integration_reserved/        Fronteira reservada para GLPI
  local_light_ai/                   IA local ultra leve para organizar descricoes
  security_and_abuse_protection/    Sanitizacao, limites e escopo
  simulated_persistence/            Stores em memoria
  shared_kernel/                    Tipos e constantes comuns
  ticket_domain/                    Modelos e servicos de chamado
  triage_rules/                     Catalogos e regras de triagem
static_web_simulator/               HTML/CSS/JS sem framework
tests/                              Testes pytest
docs/                               Planos e visao de arquitetura
```

## Pasta GLPI reservada

`app/glpi_integration_reserved/` contem a interface `GLPIClientInterface`, o `GLPIMockClient`, builders de payload, mapeamento de categorias, lookup de usuario, sessao e guardas de permissao. A integracao real futura deve substituir o mock por um cliente REST do GLPI, mantendo o motor conversacional e os canais sem regra de negocio duplicada.

## Plano futuro GLPI

- Implementar `GLPIFutureRealClient` usando a API REST do GLPI.
- Usar tokens vindos de variaveis de ambiente ou cofre corporativo.
- Mapear categorias internas para IDs reais do GLPI.
- Garantir que consultas e complementos sejam sempre escopados ao usuario autenticado.
- Evitar escrita direta no banco do GLPI; SQL futuro, se existir, deve ser somente leitura controlada, diagnostico ou auditoria.

## Planos futuros por canal

Telegram, WhatsApp e Microsoft Teams devem entrar apenas como adaptadores em `app/channel_adapters/`. Eles devem normalizar mensagens, resolver identidade do canal e chamar o mesmo `ConversationFlowController`.

## Cuidados de seguranca

- O chat bloqueia padroes SQL e comandos administrativos.
- O usuario nao consegue consultar chamados de outro usuario.
- O simulador limita tamanho de mensagem e taxa por sessao.
- O frontend usa `textContent`, evitando renderizar HTML vindo das mensagens.
- Nenhuma credencial real deve ser commitada.

## IA generativa local

A organizacao da descricao usa `app/local_light_ai/generative_description_organizer.py`, chamando um modelo generativo local via Ollama.

Caracteristicas:

- roda localmente, em CPU;
- nao chama API externa;
- nao usa OpenAI API;
- nao usa regex ou regras deterministicas para reescrever descricao;
- retorna JSON estruturado;
- pode pedir esclarecimento quando o texto estiver confuso;
- nao inventa causa, sistema, urgencia ou solucao;
- atua somente na organizacao de descricoes e complementos.

Parametrizacao:

- `LOCAL_LIGHT_AI_MODE=generative_ollama`
- `OLLAMA_BASE_URL=http://127.0.0.1:11434`
- `LOCAL_GENERATIVE_MODEL=hf.co/Qwen/Qwen3-0.6B-GGUF:Q8_0`
- `LOCAL_GENERATIVE_TIMEOUT_SECONDS=30`

Para preparar a IA local:

```bash
ollama pull hf.co/Qwen/Qwen3-0.6B-GGUF:Q8_0
```

Se o Ollama ou o modelo nao estiverem disponiveis, o fluxo nao usa fallback legado: o bot informa que a IA generativa local esta indisponivel e pede nova tentativa apos correcao do runtime.
