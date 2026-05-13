# Integracao Microsoft Teams

O Microsoft Teams usa um adaptador proprio para traduzir activities do Bot Framework em chamadas normalizadas ao `ConversationFlowController`.

Regras de triagem, categoria, gravidade e abertura de chamado continuam no motor conversacional. O adaptador so cuida de transporte, identidade do canal, conversation reference e renderizacao propria do Teams.

## Endpoint

- Rota do bot: `POST /api/teams/messages`
- Em producao, publique essa rota por reverse proxy HTTPS.
- Configure o endpoint publico no Microsoft Bot/Teams app usando `TEAMS_PUBLIC_BOT_ENDPOINT`.

## Autenticacao

- O primeiro rollout usa confirmacao por CPF, igual ao WhatsApp.
- O vinculo fica em `channel_link:teams:<teams_user_id>`.
- O desenho separa normalizacao por canal para facilitar troca futura por LDAP/Entra sem refatorar o fluxo de chamados.

## Variaveis

```env
TEAMS_ENABLED=false
TEAMS_APP_ID=
TEAMS_APP_PASSWORD=
TEAMS_TENANT_ID=
TEAMS_PUBLIC_BOT_ENDPOINT=https://seu-dominio/api/teams/messages
TEAMS_AUTH_VALIDATION_ENABLED=true
TEAMS_CONNECTOR_TIMEOUT_SECONDS=8
```

## Notificacoes

- O Teams salva conversation references em Redis para mensagens proativas.
- Cards adaptativos sao usados para eventos de ticket e abertura de chamado.
- WhatsApp continua independente, usando o dispatcher atual.
