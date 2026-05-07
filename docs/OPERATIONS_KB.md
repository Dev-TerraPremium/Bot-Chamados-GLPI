# Bot-Chamados-GLPI Operations KB

Este documento e a base de conhecimento operacional do Bot-Chamados-GLPI.
Ele foi escrito para humanos e para outras inteligencias artificiais que
precisem manter a aplicacao sem redescobrir a arquitetura toda vez.

## Resumo executivo

- Ambiente produtivo atual: LXC Proxmox em `192.168.2.110`.
- Diretorio remoto padrao: `/opt/bot-chamados-glpi`.
- Orquestracao: Docker Compose via `compose.yml`.
- API FastAPI: container `bot-chamados-web`, porta `8000`.
- WhatsApp: container `bot-chamados-whatsapp`.
- Estado e vinculos: Redis `bot-chamados-redis`.
- IA local: Ollama `bot-chamados-ollama`, modelo configurado em `.env.docker`.
- GLPI real: `https://admglpi.terrapremium.com.br/glpi/apirest.php`.

## Regra de ouro

Use `botctl` dentro do terminal do LXC.

Depois do deploy, o script `remote-deploy.sh` instala:

```bash
/usr/local/bin/botctl -> /opt/bot-chamados-glpi/scripts/botctl.py
```

Abra o painel interativo:

```bash
botctl
```

Ou use comandos diretos:

```bash
botctl status
botctl doctor
botctl logs whatsapp -f
botctl allowlist show
botctl redis delete-link 66999990980
```

## Fluxo mental da aplicacao

```text
WhatsApp
  -> bot-chamados-whatsapp
  -> POST http://web:8000/api/conversation/message
  -> bot-chamados-web
  -> Redis para estado, vinculo, lock e filas
  -> GLPI REST para usuario/chamados
  -> Celery workers para tarefas de IA e GLPI
  -> Ollama para IA local
```

## Comandos essenciais

### Ver estado geral

```bash
botctl status
```

Mostra:

- `docker compose ps`
- `/health`
- `/health/runtime`
- `/health/glpi`
- configuracao resumida e redigida, sem vazar tokens

### Diagnostico completo

```bash
botctl doctor
```

Use quando algo "nao faz sentido". Ele confere projeto, env, Docker, health
e status geral.

### Subir aplicacao

```bash
botctl up
```

Com rebuild:

```bash
botctl up --build
```

Subir apenas servicos especificos:

```bash
botctl up web worker-ai worker-glpi
```

### Descer aplicacao

```bash
botctl down
```

Nao use `--volumes` em producao sem entender o impacto. Volumes guardam Redis,
Ollama e sessao do WhatsApp.

Se realmente precisar remover volumes:

```bash
botctl down --volumes
```

Ele pede confirmacao digitando `SIM`.

### Reiniciar servicos

```bash
botctl restart whatsapp
botctl restart web
botctl restart worker-ai worker-glpi
botctl restart
```

### Logs

WhatsApp ao vivo, inclusive QR/conexao:

```bash
botctl qr
botctl logs whatsapp -f
```

Web/API:

```bash
botctl logs web --tail 200
botctl logs web -f
```

Todos:

```bash
botctl logs all --tail 200
```

Servicos validos:

- `web`
- `whatsapp`
- `worker-ai`
- `worker-glpi`
- `redis`
- `ollama`
- `all`

## Allowlist do WhatsApp

O conector WhatsApp respeita:

- `ALLOWED_NUMBERS`
- `ALLOW_ALL_NUMBERS`
- `LOG_IGNORED_MESSAGES`

Ver allowlist:

```bash
botctl allowlist show
```

Adicionar numero:

```bash
botctl allowlist add 66999990980
botctl restart whatsapp
```

Remover numero:

```bash
botctl allowlist remove 66999990980
botctl restart whatsapp
```

Substituir lista:

```bash
botctl allowlist set 66999990980,66988887777
botctl restart whatsapp
```

Liberar qualquer numero, apenas para teste controlado:

```bash
botctl allowlist all-on
botctl restart whatsapp
```

Voltar modo seguro:

```bash
botctl allowlist all-off
botctl restart whatsapp
```

## Autenticacao e vinculo de canal

Quando um telefone fala com o bot pela primeira vez:

1. O bot cria chave Redis `channel_link:whatsapp:<telefone>`.
2. Responde pedindo os primeiros digitos do CPF.
3. Consulta usuario no GLPI cruzando telefone + CPF parcial.
4. Se encontra exatamente 1 usuario, grava vinculo ativo no Redis.

Ver chaves de vinculo:

```bash
botctl redis keys
```

Ver vinculo de um telefone:

```bash
botctl redis show-link 66999990980
```

Apagar so o vinculo de um telefone, sem destruir todo o Redis:

```bash
botctl redis delete-link 66999990980
```

Evite `FLUSHALL`. So use como ultimo recurso:

```bash
botctl redis flush
```

Ele pede confirmacao digitando `SIM`.

## Problema corrigido em 2026-05-07

Sintoma:

```text
Nao consegui confirmar seus dados. Verifique os digitos informados...
```

Causas encontradas:

1. `.env.docker` estava usando URL GLPI errada:
   `https://admglpi.terrapremium.com.br/apirest.php`
2. URL correta:
   `https://admglpi.terrapremium.com.br/glpi/apirest.php`
3. O lookup de usuario era rigido para CPF/telefone:
   - CPF aceitava apenas pontuacao simples.
   - Campo de CPF precisava ser `registration_number`.
   - Busca de telefone dependia de match muito direto.

Correcoes aplicadas:

- CPF agora mantem somente digitos.
- Lookup aceita campo `cpf` ou nome `CPF`/`Documento`, alem de
  `registration_number`.
- Busca telefone por variantes completas, ultimos 8 digitos e ultimos
  4 digitos.
- Apos buscar de forma ampla, o codigo filtra por telefone normalizado para
  reduzir falso positivo.
- Logs estruturados foram adicionados:
  - `glpi_user_phone_search_completed`
  - `glpi_user_identity_lookup_completed`

Evidencia apos deploy:

- `/health/glpi` retornou `status: ok`.
- `initSession`, `changeActiveProfile`, `changeActiveEntities`,
  `listSearchOptions/User`, `listSearchOptions/ITILCategory` e
  `listSearchOptions/Ticket` retornaram OK.
- Smoke test via API com telefone `66999990980` e CPF parcial `0991` retornou
  vinculo criado para `glpi_user_id=266`.
- Depois do smoke test, o vinculo foi removido para permitir teste real pelo
  WhatsApp.

## Healthchecks

Dentro do LXC:

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/health/runtime
curl -s http://127.0.0.1:8000/health/glpi
```

Via `botctl`:

```bash
botctl status
```

Se `/health/glpi` retornar `degraded`, verifique:

1. `GLPI_BASE_URL`
2. `GLPI_APP_TOKEN`
3. `GLPI_USER_TOKEN`
4. `GLPI_DEFAULT_PROFILE_ID`
5. `GLPI_DEFAULT_ENTITY_ID`
6. Logs do web:

```bash
botctl logs web --tail 200
```

## Deploy remoto

Do Windows/local, o fluxo atual envia tarball, `.env.docker` e
`remote-deploy.sh` via SSH para o LXC. O documento historico e:

```text
docs/DEPLOY_AND_TROUBLESHOOTING.md
```

No LXC, o deploy:

1. Confere dependencias.
2. Confere Docker.
3. Confere `.env.docker`.
4. Instala `botctl`.
5. Sobe containers com `docker compose up -d --build`.
6. Mostra status e health.

## Arquivos importantes

- `compose.yml`: definicao da stack.
- `.env.docker`: configuracao produtiva usada pelos containers.
- `remote-deploy.sh`: deploy executado dentro do LXC.
- `deploy_via_ssh.py`: deploy via Paramiko quando a maquina local tem a lib.
- `scripts/botctl.py`: painel terminal do LXC.
- `docs/DEPLOY_AND_TROUBLESHOOTING.md`: historico de deploy e diagnostico.
- `docs/OPERATIONS_KB.md`: este documento.

## Procedimento padrao para outra IA

Ao receber um problema operacional:

1. Leia `docs/OPERATIONS_KB.md`.
2. Rode no LXC:

```bash
botctl status
botctl doctor
```

3. Se for WhatsApp:

```bash
botctl logs whatsapp --tail 200
botctl allowlist show
```

4. Se for autenticacao:

```bash
botctl logs web --tail 250
botctl redis show-link <telefone>
```

5. Para retestar autenticacao do zero:

```bash
botctl redis delete-link <telefone>
```

6. Evite `botctl redis flush` salvo com confirmacao explicita do usuario.
7. Antes de alterar `.env.docker`, explique a mudanca e depois reinicie os
   servicos afetados.
8. Nunca publique tokens nos logs ou respostas.

## Smoke test manual de autenticacao

Use apenas em manutencao controlada:

```bash
curl -s -X POST http://127.0.0.1:8000/api/conversation/message \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"ops-check","channel":"whatsapp","channel_identifier":"66999990980","message":"Oi"}'

curl -s -X POST http://127.0.0.1:8000/api/conversation/message \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"ops-check","channel":"whatsapp","channel_identifier":"66999990980","message":"0991"}'
```

Depois limpe o vinculo criado:

```bash
botctl redis delete-link 66999990980
```

## Recuperacao rapida

Aplicacao nao responde:

```bash
botctl status
botctl logs web --tail 200
botctl restart web
```

WhatsApp nao responde:

```bash
botctl allowlist show
botctl logs whatsapp --tail 200
botctl restart whatsapp
```

GLPI falha:

```bash
botctl env get GLPI_BASE_URL
botctl logs web --tail 250
botctl status
```

IA/Ollama falha:

```bash
botctl logs ollama --tail 200
botctl restart ollama worker-ai
```

Redis suspeito:

```bash
botctl logs redis --tail 200
botctl redis keys
```

## Decisoes de seguranca

- `botctl env show` redige tokens e segredos.
- `botctl down --volumes` pede confirmacao.
- `botctl redis flush` pede confirmacao.
- Allowlist nunca deve ficar em `ALLOW_ALL_NUMBERS=true` em producao sem
  motivo claro e janela controlada.
- Para desbloquear autenticacao de um usuario, prefira apagar somente a chave
  `channel_link:whatsapp:<telefone>`.
