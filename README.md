# Assistente de Chamados TI On-Premise

Base de um bot corporativo on-premise para triagem, abertura, consulta e complemento de chamados de TI, com simulador web, GLPI em modo mock ou real, Redis/Celery para concorrência produtiva e IA local leve via Ollama.

## Objetivo

Este projeto cria a fundação modular do "Assistente de Chamados TI On-Premise" usando Python, FastAPI e um simulador web em HTML/CSS/JavaScript puro. O foco é manter um motor único de conversa, preparado para múltiplos canais, com regras de negócio isoladas dos adaptadores.

## Escopo do MVP

- Autenticação simulada do usuário Pedro Torres, ainda sem autenticação definitiva.
- Motor de conversa orientado por estados.
- Abertura única de chamado, sem duplicidade entre rápido e detalhado.
- Atribuição automática de categoria por descrição, com escolha manual opcional.
- Categoria "Outro" com confirmação explícita.
- Organização do texto do usuário com IA local ultra leve para português.
- Mapeamento de impacto para gravidade.
- Resumo antes da criação do chamado.
- Criação, consulta e complemento em modo mock ou GLPI real via API REST.
- Redis para estado, rate limit, lock por sessão e idempotência em modo produtivo.
- Celery Worker para filas de IA local e GLPI.
- Proteções contra abuso, SQL digitado, comandos, prompt injection e texto excessivo.
- Pasta isolada para integração GLPI.

## Ainda nao implementado

Ainda não há autenticação definitiva, Telegram real, WhatsApp real, Microsoft Teams real, upload real de anexos ou envio de mensagens externas. A integração GLPI real já existe por API REST, mas deve ser ativada por variáveis de ambiente e validada com credenciais fora do Git.

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

O `requirements.txt` instala as dependências Python da aplicação, incluindo FastAPI, Redis, Celery, HTTPX e testes. A IA generativa local roda em um runtime on-premise separado, via Ollama, usando por padrão o modelo `hf.co/Qwen/Qwen3-0.6B-GGUF:Q8_0`.

## Rodar

Modo local simples, usando memória e GLPI mock:

```bash
uvicorn app.main:app --reload
```

Depois acesse:

[http://localhost:8000](http://localhost:8000)

Modo local produtivo, usando Redis/Celery:

```powershell
copy .env.example .env.local
```

Edite `.env.local` com os valores reais e use:

```env
GLPI_INTEGRATION_MODE=real
STATE_BACKEND=redis
USE_CELERY_WORKERS=true
EXPOSE_DEBUG_ROUTES=false
GLPI_BASE_URL=https://admglpi.terrapremium.com.br/glpi/apirest.php
GLPI_DEFAULT_ENTITY_ID=3
GLPI_DEFAULT_PROFILE_ID=4
GLPI_DEFAULT_REQUESTER_USER_ID=266
```

Inicie Redis localmente e suba os workers:

```powershell
python -m celery -A app.background_jobs.celery_app.celery_app worker -Q ai_local --pool=solo --concurrency=1 --loglevel=INFO
python -m celery -A app.background_jobs.celery_app.celery_app worker -Q glpi_io --pool=solo --concurrency=4 --loglevel=INFO
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

No Windows, `--pool=solo` evita problemas de fork. Em Linux/container, o pool pode ser ajustado conforme CPU e memória.

## Rodar com Docker

Para validar a stack completa com Redis e workers Celery sem depender de GLPI real ou Ollama real:

```bash
docker compose up --build -d
docker compose ps
docker compose logs -f web worker-ai worker-glpi
```

O arquivo [`.env.docker`](/Users/paletotcode/Documents/Bot-Chamados-GLPI/.env.docker) sobe a aplicação com Redis/Celery e IA local real via Ollama no host:

- `STATE_BACKEND=redis`
- `USE_CELERY_WORKERS=true`
- `GLPI_INTEGRATION_MODE=mock`
- `LOCAL_LIGHT_AI_MODE=generative_ollama`
- `OLLAMA_BASE_URL=http://host.docker.internal:11434`
- `LOCAL_GENERATIVE_MODEL=hf.co/Qwen/Qwen3-0.6B-GGUF:Q8_0`
- `AI_GUIDED_DETAILING_ENABLED=true`
- `AI_MAX_CLARIFICATION_QUESTIONS=5`

Isso força o caminho completo de filas sem depender de GLPI real. O worker GLPI roda em `glpi_io`, o worker de IA em `ai_local`, e o modelo generativo roda localmente no host via Ollama. Quando a descrição inicial estiver vaga, a IA pode fazer até 5 perguntas curtas, uma por vez, antes de sugerir a categoria.

Healthchecks úteis:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/runtime
```

Smoke test automatizado:

```bash
python scripts/docker_smoke_test.py
```

Encerramento:

```bash
docker compose down
```

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
  distributed_runtime/              Redis, locks, rate limit e idempotencia
  background_jobs/                   Celery app, tasks e wrappers
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

`app/glpi_integration_reserved/` contém a interface `GLPIClientInterface`, o `GLPIMockClient`, o `GLPIRealClient`, builders de payload, mapeamento de categorias, lookup de usuário, sessão e guardas de permissão. O motor conversacional escolhe mock ou real por configuração, mantendo canais sem regra de negócio duplicada.

## Integração GLPI

- `GLPIRealClient` usa API REST do GLPI.
- Tokens vêm de variáveis de ambiente ou cofre corporativo.
- Categorias internas são mapeadas para IDs reais do GLPI.
- Consultas e complementos passam por escopo de usuário.
- Escrita direta no banco do GLPI não é usada para abertura, alteração ou complemento.
- SQL, quando existir, deve ser somente leitura controlada, diagnóstico ou auditoria.

## Planos futuros por canal

Telegram, WhatsApp e Microsoft Teams devem entrar apenas como adaptadores em `app/channel_adapters/`. Eles devem normalizar mensagens, resolver identidade do canal e chamar o mesmo `ConversationFlowController`.

## Cuidados de seguranca

- O chat bloqueia padrões SQL, comandos administrativos e prompt injection.
- O usuário não consegue consultar chamados de outro usuário.
- O simulador limita tamanho de mensagem e taxa por sessão.
- Redis pode aplicar rate limit distribuído.
- A abertura de chamado usa idempotência para evitar duplicidade por clique duplo.
- O frontend usa `textContent`, evitando renderizar HTML vindo das mensagens.
- Nenhuma credencial real deve ser commitada.

## IA generativa local

A organizacao da descricao usa `app/local_light_ai/generative_description_organizer.py`, chamando um modelo generativo local via Ollama.

Caracteristicas:

- roda localmente, em CPU;
- não chama API externa;
- não usa OpenAI API;
- não usa regex ou regras determinísticas para reescrever descrição;
- retorna JSON estruturado;
- pode pedir esclarecimento quando o texto estiver confuso;
- não inventa causa, sistema, urgência ou solução;
- atua somente na organização de descrições e complementos;
- possui limite de entrada, saída, timeout, temperatura e tokens.

Parametrizacao:

- `LOCAL_LIGHT_AI_MODE=generative_ollama`
- `OLLAMA_BASE_URL=http://127.0.0.1:11434`
- `LOCAL_GENERATIVE_MODEL=hf.co/Qwen/Qwen3-0.6B-GGUF:Q8_0`
- `LOCAL_GENERATIVE_TIMEOUT_SECONDS=30`
- `AI_GUIDED_DETAILING_ENABLED=true`
- `AI_MAX_CLARIFICATION_QUESTIONS=5`
- `AI_MAX_INPUT_CHARS=1000`
- `AI_MAX_OUTPUT_CHARS=800`
- `AI_OLLAMA_NUM_PREDICT=180`
- `AI_OLLAMA_TEMPERATURE=0.1`

Para preparar a IA local:

```bash
ollama pull hf.co/Qwen/Qwen3-0.6B-GGUF:Q8_0
```

Se o Ollama ou o modelo não estiverem disponíveis, o fluxo não usa fallback legado: o bot informa que a IA generativa local está indisponível e pede nova tentativa após correção do runtime.

## Plano de implementacao para producao GLPI

Status: implementado no código, exceto autenticação definitiva, que está deliberadamente pendente.

Este plano descreve a evolução do MVP local para uma versão produtiva inicial, mantendo a arquitetura multicanal e sem duplicar regra de negócio nos canais.

### Objetivo da proxima entrega

Transformar o simulador atual em uma aplicacao produtiva controlada, capaz de abrir, consultar e complementar chamados reais no GLPI via API REST, com autenticacao real de usuario, validacao rigorosa de todas as acoes do menu, concorrencia segura com Redis e Celery Worker, e IA local limitada para organizacao de descricao, correcao ortografica e apoio de classificacao.

### Premissas

- A integracao oficial com o GLPI sera feita via API REST.
- Nao sera feita escrita direta no banco MySQL do GLPI para abrir, alterar ou complementar chamados.
- SQL no banco GLPI fica reservado apenas para diagnostico, leitura controlada, auditoria e mapeamentos administrativos.
- O primeiro ambiente produtivo sera testado na maquina local.
- No futuro, a hospedagem sera em container no Proxmox, nao em VM tradicional.
- A IA local nao tera memoria de usuario, historico semantico ou base vetorial nesta fase.
- Redis sera usado para concorrencia, filas, estado operacional e controles de seguranca, nao como memoria cognitiva da IA.
- Tokens e credenciais reais nunca devem ser commitados.
- Os tokens ja compartilhados durante validacao devem ser rotacionados antes de producao definitiva.

### Arquitetura alvo

```text
Web Simulator / futuros canais
        |
        v
Channel Adapters
        |
        v
Conversation Engine
        |
        +--> Validadores de menu, seguranca e escopo
        |
        +--> Redis
        |      - estado de conversa com TTL
        |      - rate limit distribuido
        |      - locks por sessao
        |      - idempotencia de abertura de chamado
        |      - broker/result backend do Celery
        |
        +--> Celery Worker
        |      - fila glpi_io
        |      - fila ai_local
        |      - fila maintenance
        |
        +--> Servicos de dominio
        |
        +--> GLPI REST Client
        |
        v
GLPI real
```

### Fase 1: configuracao produtiva e secrets

Criar uma camada de configuracao produtiva com validacao forte de ambiente.

Itens:

- Expandir `AppSettings` e `GLPIIntegrationConfig`.
- Separar claramente `local`, `staging` e `production`.
- Exigir variaveis obrigatorias quando `APP_ENV=production`.
- Adicionar suporte a `.env.local` para teste local real sem commit.
- Atualizar `.env.example` sem credenciais reais.
- Bloquear inicializacao em modo real se faltar `GLPI_BASE_URL`, `GLPI_APP_TOKEN`, `GLPI_USER_TOKEN`, `GLPI_DEFAULT_ENTITY_ID` ou mapeamento minimo de categoria.
- Registrar logs sem imprimir tokens, session tokens ou dados sensiveis.

Variaveis planejadas:

```env
APP_ENV=local
GLPI_INTEGRATION_MODE=real
GLPI_BASE_URL=https://admglpi.terrapremium.com.br/glpi/apirest.php
GLPI_DEFAULT_ENTITY_ID=3
GLPI_DEFAULT_REQUESTER_USER_ID=266
GLPI_APP_TOKEN=
GLPI_USER_TOKEN=

REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

AI_QUEUE_NAME=ai_local
AI_MAX_CONCURRENT_TASKS=1
AI_TASK_TIMEOUT_SECONDS=25
AI_MAX_INPUT_CHARS=1000
AI_MAX_OUTPUT_CHARS=800
AI_OLLAMA_NUM_PREDICT=180
AI_OLLAMA_TEMPERATURE=0.1

GLPI_QUEUE_NAME=glpi_io
GLPI_HTTP_TIMEOUT_SECONDS=20
GLPI_SESSION_TTL_SECONDS=600
GLPI_CREATE_TICKET_IDEMPOTENCY_TTL_SECONDS=300

SESSION_TTL_SECONDS=3600
RATE_LIMIT_MESSAGES_PER_MINUTE=20
RATE_LIMIT_MESSAGES_PER_HOUR=200
```

### Fase 2: cliente GLPI real

Implementar o `GLPIFutureRealClient` como cliente real e renomear para uma classe final de producao, mantendo a interface `GLPIClientInterface`.

Itens:

- Implementar `init_session`.
- Implementar `kill_session`.
- Implementar `create_ticket`.
- Implementar `get_my_tickets`.
- Implementar `get_ticket_by_id`.
- Implementar `add_followup`.
- Implementar `find_user_by_identifier`.
- Implementar `find_category_by_name`.
- Usar `httpx` com timeout, tratamento de erro e redacao de credenciais em logs.
- Usar sempre HTTPS.
- Nao seguir redirect HTTP para HTTPS como dependencia de producao.
- Tratar erros GLPI com mensagens controladas ao usuario.
- Garantir que o motor de conversa nao conheca detalhes da API GLPI.

Payload inicial de abertura:

```json
{
  "input": {
    "name": "Titulo sugerido",
    "content": "Descricao organizada e resumo operacional",
    "entities_id": 3,
    "itilcategories_id": 455,
    "_users_id_requester": 266,
    "urgency": 3,
    "impact": 3,
    "priority": 4,
    "status": 1
  }
}
```

Observacao: os IDs reais de categoria devem vir de configuracao ou tabela de mapeamento, nao ficar espalhados no fluxo conversacional.

### Fase 3: mapeamento GLPI de categorias e severidade

Criar uma fronteira explicita entre categorias do bot e categorias reais do GLPI.

Itens:

- Criar catalogo de mapeamento por ambiente.
- Validar se a categoria GLPI existe antes de abrir chamado.
- Validar se a categoria e permitida para helpdesk quando aplicavel.
- Registrar fallback controlado para `Outro`.
- Permitir troca futura para mapeamento carregado do GLPI.
- Testar cada categoria do menu contra o ID real configurado.

Mapeamento inicial planejado:

```text
Internet / Rede -> 535
Computador / Notebook -> 455
Impressora -> 490
Sistema / ERP -> 622
E-mail / Microsoft 365 -> 487
Acesso / Senha -> 416
Telefonia -> 587
GLPI -> 647
Solicitacao de equipamento -> 639
Cameras / CFTV -> 445
Ubiquiti / Wi-Fi -> 544
Outro -> 659
```

### Fase 4: Redis como base de concorrencia operacional

Substituir controles locais em memoria por componentes distribuidos em Redis.

Itens:

- Criar `redis_connection.py` em camada de infraestrutura/configuracao.
- Criar `RedisConversationStore`.
- Criar `RedisRateLimiter`.
- Criar `RedisSessionLock`.
- Criar `RedisIdempotencyStore`.
- Manter TTL por sessao para evitar crescimento indefinido.
- Usar lock por `session_id` para impedir duas mensagens simultaneas alterando o mesmo contexto.
- Criar chave de idempotencia para abertura de ticket, evitando duplicidade se o usuario clicar duas vezes ou reenviar a confirmacao.
- Remover dependencia de estado em memoria para fluxo produtivo.

Chaves planejadas:

```text
conversation:{session_id}
lock:conversation:{session_id}
ratelimit:minute:{identity_or_session}
ratelimit:hour:{identity_or_session}
ticket_idempotency:{session_id}:{draft_hash}
glpi_session:{integration_user}
```

### Fase 5: Celery Worker

Adicionar Celery para isolar tarefas lentas, controlar concorrencia e evitar que chamadas GLPI/IA bloqueiem o processo web.

Filas:

```text
ai_local      Organizacao de descricao, correcao ortografica, apoio de classificacao
glpi_io       Criacao, consulta e complemento de chamados no GLPI
maintenance   Tarefas futuras de limpeza, healthcheck e sincronizacao leve
```

Tarefas planejadas:

- `organize_description_task`
- `suggest_category_task`
- `create_glpi_ticket_task`
- `query_glpi_tickets_task`
- `add_glpi_followup_task`
- `validate_glpi_mapping_task`

Controles obrigatorios:

- Time limit por tarefa.
- Soft time limit para encerrar com resposta amigavel.
- Retry controlado para erro transitorio de rede.
- Sem retry automatico em erro de validacao ou permissao.
- Idempotencia em criacao de ticket.
- Separacao de worker de IA e worker de GLPI.
- Concorrencia baixa para fila de IA local.
- Concorrencia maior e limitada para fila GLPI.

Fluxo da API:

```text
POST /api/conversation/message
  -> sanitiza entrada
  -> valida estado e opcao
  -> aplica lock por sessao
  -> quando precisar de IA/GLPI, cria tarefa Celery
  -> responde com estado "processando" ou aguarda curto prazo configurado
  -> frontend consulta resultado se necessario
```

Para manter a experiencia de chat fluida, a implementacao deve preferir aguardar um curto periodo configuravel. Se a tarefa ultrapassar esse tempo, o bot responde que esta processando e o frontend faz polling controlado.

### Fase 6: IA local com limite de consumo e seguranca

Manter o modelo local via Ollama, sem memoria longa e sem historico persistente fora da sessao. Para detalhamento guiado, a aplicacao guarda apenas uma memoria curta de perguntas/respostas no contexto Redis da conversa.

Itens:

- Criar uma fila Celery exclusiva para IA.
- Limitar concorrencia da fila `ai_local`.
- Limitar tamanho de entrada antes da chamada ao modelo.
- Limitar tamanho maximo de saida aceita.
- Configurar temperatura baixa.
- Configurar limite de tokens de resposta.
- Sanitizar prompt e resposta.
- Validar que a resposta e JSON no schema esperado.
- Rejeitar resposta que tente alterar categoria, gravidade ou acao sem confirmacao do usuario.
- Aplicar timeout curto.
- Nao enviar tokens, sessoes, e-mail sensivel ou credenciais para a IA.
- Nao registrar prompt completo em log produtivo.
- Nao manter memoria da IA em Redis.

Responsabilidades permitidas para IA:

- Organizar descricao curta.
- Corrigir ortografia e gramatica com minimo de alteracao.
- Identificar quando o texto esta confuso e pedir esclarecimento.
- Sugerir categoria provavel, sempre com confirmacao humana.

Responsabilidades proibidas para IA:

- Abrir chamado sozinha.
- Escolher gravidade final sem regra deterministica.
- Consultar GLPI.
- Gerar SQL.
- Executar comandos.
- Alterar permissao.
- Inventar causa, solucao ou impacto.
- Decidir em nome do usuario.

### Fase 7: validacao obrigatoria de todas as acoes do menu

Fortalecer o motor de conversa para que toda entrada seja validada pelo estado atual.

Itens:

- Criar validadores por estado.
- Aceitar apenas opcoes permitidas no estado atual.
- Rejeitar numeros fora do menu.
- Rejeitar texto livre quando o estado exige opcao numerica.
- Rejeitar opcao numerica quando o estado exige descricao.
- Confirmar explicitamente acoes destrutivas ou finais.
- Garantir que `cancelar`, `voltar`, `sair` e `reiniciar` tenham comportamento seguro.
- Garantir que correcao de informacoes volte ao ponto certo do fluxo.
- Garantir que complemento de chamado exija propriedade e status valido.
- Garantir que consulta por numero nunca revele chamado de outro usuario.
- Criar testes para cada estado e cada opcao invalida importante.

Exemplo de regra:

```text
Estado: confirmacao_de_abertura
Permitido: 1, 2, 3
Entrada "abrir tudo", "sim por favor", "999", "DROP TABLE" ou "<script>"
Resultado: mensagem controlada, sem transicao indevida
```

### Fase 8: autenticacao definitiva do usuario

Substituir a autenticacao simulada por uma estrategia real e segura.

Etapa imediata para piloto:

- Rodar com usuario GLPI fixo e controlado somente para teste.
- Registrar claramente que todos os chamados sairao em nome desse usuario.
- Nao liberar para uso amplo nessa modalidade.

Etapa definitiva:

- Criar `AuthenticationServiceInterface`.
- Implementar autenticacao web real.
- Resolver usuario autenticado para `glpi_user_id`.
- Criar sessao web assinada e expirada.
- Nao armazenar senha.
- Nao gravar token individual do usuario no banco ou log.
- Vincular `session_id` a identidade autenticada.
- Criar `ChannelIdentityLinkService` para futuros canais.
- Validar escopo por usuario em toda consulta e complemento.

Alternativas tecnicas a validar:

```text
Opcao A: login via GLPI API
  Usuario informa login/senha no portal interno.
  Backend valida contra GLPI/AD integrado.
  Aplicacao guarda apenas sessao propria com TTL.

Opcao B: AD/LDAP corporativo
  Usuario autentica no AD.
  Backend mapeia login/e-mail para usuario GLPI.
  Melhor caminho para producao corporativa.

Opcao C: SSO/reverse proxy futuro
  Proxy autentica usuario.
  Aplicacao recebe identidade confiavel por header interno.
  Requer forte controle de rede e headers.
```

Recomendacao: usar AD/LDAP ou o mecanismo corporativo ja integrado ao GLPI, com mapeamento seguro para `glpi_user_id`. Para piloto local, usar seu usuario GLPI e limitar acesso.

### Fase 9: seguranca de aplicacao

Itens:

- Remover endpoint de debug em producao.
- Bloquear CORS aberto.
- Adicionar headers de seguranca no frontend.
- Criar CSRF/session strategy para web.
- Usar cookies seguros quando houver login real.
- Redigir tokens e session tokens em logs.
- Rate limit por usuario autenticado e por IP.
- Registrar auditoria de abertura, consulta e complemento.
- Validar payloads com modelos Pydantic.
- Garantir que HTML do usuario nunca seja renderizado.
- Criar resposta padrao para tentativa suspeita.
- Criar testes para SQL injection, script injection, prompt injection e texto excessivo.

### Fase 10: observabilidade e operacao

Itens:

- Logs estruturados com `request_id`, `session_id` anonimizado e `user_id`.
- Healthcheck do FastAPI.
- Healthcheck do Redis.
- Healthcheck do Celery.
- Healthcheck do Ollama.
- Healthcheck do GLPI.
- Endpoint interno de status sem dados sensiveis.
- Metricas basicas: mensagens por minuto, tempo de IA, tempo GLPI, falhas por tipo.
- Log de auditoria para chamados reais.
- Guia de troubleshooting.

### Fase 11: testes obrigatorios antes de producao

Testes unitarios:

- Validadores de menu por estado.
- Mapeamento de categoria.
- Mapeamento de gravidade.
- Sanitizacao.
- Rate limit Redis.
- Idempotencia.
- Escopo de usuario.
- Parser de resposta da IA.

Testes de integracao local:

- Redis real local.
- Celery worker real local.
- Ollama real local.
- GLPI real em modo controlado.
- Criacao real de chamado de teste.
- Consulta real do chamado criado.
- Complemento real do chamado criado.
- Tentativa de consultar chamado de outro usuario.

Teste de concorrencia minimo:

- 100 sessoes diferentes.
- 100 mensagens simultaneas em estados diferentes.
- Multiplas descricoes chamando IA com fila limitada.
- Cliques duplicados em confirmar abertura.
- Queda temporaria do GLPI.
- Queda temporaria do Ollama.

Meta minima:

```text
Sem duplicar ticket em clique duplo.
Sem vazar ticket de outro usuario.
Sem travar API web por fila de IA.
Sem imprimir tokens em logs.
Sem perder estado da conversa durante concorrencia.
```

### Fase 12: container futuro para Proxmox

A implementacao deve nascer preparada para container, mas a primeira validacao sera local.

Componentes futuros:

```text
container-web        FastAPI/Gunicorn/Uvicorn workers
container-worker-ai  Celery worker fila ai_local
container-worker-glpi Celery worker fila glpi_io
container-redis      Redis
container-ollama     Ollama/modelo local, se fizer sentido operacional
reverse-proxy        Nginx/Traefik/Caddy
```

Cuidados:

- Volumes separados para modelo Ollama.
- Secrets fora da imagem.
- Healthchecks por container.
- Restart automatico.
- Logs centralizados.
- Rede interna entre containers.
- Exposicao publica somente do reverse proxy.

### Ordem recomendada de implementacao

1. Corrigir configuracoes e secrets.
2. Implementar cliente GLPI real.
3. Implementar mapeamento real de categorias.
4. Plugar `GLPI_INTEGRATION_MODE=real`.
5. Implementar Redis para estado, rate limit, locks e idempotencia.
6. Implementar Celery e filas.
7. Migrar IA local para fila `ai_local`.
8. Migrar chamadas GLPI para fila `glpi_io`.
9. Fortalecer validadores de menu por estado.
10. Implementar autenticacao real ou piloto controlado com usuario fixo.
11. Remover debug de producao e endurecer seguranca.
12. Criar testes de concorrencia e integracao.
13. Rodar piloto local criando chamado real controlado.
14. Preparar container para Proxmox.

### Criterios de aceite

- A aplicacao abre chamado real no GLPI via API REST.
- A aplicacao consulta somente chamados do usuario autenticado.
- A aplicacao complementa somente chamados permitidos do usuario autenticado.
- Nenhuma regra de negocio fica no frontend.
- Toda entrada do menu e validada pelo estado atual.
- Redis controla estado, rate limit, lock e idempotencia em modo produtivo.
- Celery executa IA e GLPI fora do processo web.
- IA local tem timeout, limite de concorrencia, limite de entrada e limite de saida.
- Erros de GLPI, Redis, Celery e Ollama geram mensagem controlada.
- Tokens nao aparecem em logs, arquivos ou respostas HTTP.
- Teste com 100 sessoes simultaneas nao duplica chamados nem corrompe estado.
- Debug local fica desabilitado em producao.
- O projeto continua preparado para Telegram, WhatsApp e Microsoft Teams sem duplicar fluxo.

### Pendencias para validar antes da implementacao

- Confirmar se o piloto local pode usar temporariamente o usuario GLPI `pedro.torres`.
- Confirmar se a autenticacao definitiva sera AD/LDAP, GLPI login ou SSO/reverse proxy.
- Confirmar se os IDs de categoria planejados sao os finais para abertura real.
- Confirmar se o GLPI aceita abertura em categorias-pai ou se exigira categorias-filha.
- Confirmar politica de IP do Cliente de API apos o teste com intervalo aberto.
- Confirmar limite operacional desejado para IA local: 1 ou 2 tarefas simultaneas.
- Confirmar se Redis e Celery serao instalados localmente via servico nativo ou container ja na maquina de teste.
