# Status da integração Microsoft Teams

Data do registro: 13/05/2026

## Objetivo

Integrar o bot de chamados GLPI ao Microsoft Teams usando Microsoft Bot Framework / Azure Bot Service, com o Teams chamando o endpoint público:

```text
POST https://botctl.terrapremium.com.br/api/teams/messages
```

## Infraestrutura validada

- Backend do bot em produção no LXC Proxmox `bot-chamados-glpi`.
- IP interno do LXC: `192.168.2.110`.
- Backend publicado internamente na porta `8000`.
- Endpoint implementado no backend: `POST /api/teams/messages`.
- DNS público criado na KingHost:

```text
botctl.terrapremium.com.br -> 177.39.131.100
```

- FortiGate encaminha tráfego público `80/443` para o proxy central:

```text
177.39.131.100:443 -> 192.168.2.8:443
177.39.131.100:80  -> 192.168.2.8:80
```

- O servidor `192.168.2.8` é o Nginx central da empresa.
- Foi criado o site Nginx `botctl.terrapremium.com.br` apontando para:

```text
proxy_pass http://192.168.2.110:8000;
```

- `nginx -t` foi executado com sucesso.
- `systemctl reload nginx` foi executado sem queda dos serviços.
- O certificado foi corrigido com Certbot no Nginx central.

## Validação final do endpoint público

O navegador/DevTools confirmou que:

```text
GET https://botctl.terrapremium.com.br/api/teams/messages
Status: 405 Method Not Allowed
Allow: POST
Remote Address: 177.39.131.100:443
```

Esse resultado é esperado, porque a rota do Bot Framework aceita `POST`, não `GET`. Portanto, a cadeia DNS, FortiGate, Nginx, certificado HTTPS e backend ficou funcional para o endpoint do Teams.

## Credenciais Azure criadas

No Microsoft Entra ID, foi criada a App Registration:

```text
Nome: Bot Chamados GLPI Teams
Application (client) ID: 2cfe4453-e1fb-4c63-915b-45c88403deb2
Directory (tenant) ID: c9e7216a-6b68-493e-8a82-24459c1cb8c4
Tipo: Single tenant
```

Um client secret chegou a ser criado, mas foi exposto durante a operação. Ele deve ser removido e substituído por um novo secret antes de qualquer uso em produção.

## Ponto de parada

A implementação foi pausada porque a conta usada não tinha licença/permissão para criar o recurso `Azure Bot` no Azure Portal.

Sem o recurso Azure Bot, o Microsoft Teams não consegue entregar oficialmente as mensagens ao endpoint do backend, mesmo com a App Registration criada.

## Próximos passos quando a empresa liberar a continuidade

1. Remover o client secret exposto da App Registration.
2. Criar um novo client secret e copiar o valor diretamente para o ambiente seguro do servidor.
3. Criar o recurso `Azure Bot` em uma assinatura Azure autorizada.
4. Vincular o Azure Bot à App Registration existente ou usar o Microsoft App ID criado.
5. Configurar o Messaging endpoint:

```text
https://botctl.terrapremium.com.br/api/teams/messages
```

6. Habilitar o canal `Microsoft Teams` no Azure Bot.
7. Configurar o app no Teams Developer Portal usando o bot existente.
8. Escopo inicial recomendado: `Personal`.
9. Publicar/testar o app no Teams.

## Variáveis esperadas no servidor

Quando a integração for retomada, aplicar:

```env
TEAMS_ENABLED=true
TEAMS_APP_ID=2cfe4453-e1fb-4c63-915b-45c88403deb2
TEAMS_APP_PASSWORD=<novo client secret value>
TEAMS_TENANT_ID=c9e7216a-6b68-493e-8a82-24459c1cb8c4
TEAMS_PUBLIC_BOT_ENDPOINT=https://botctl.terrapremium.com.br/api/teams/messages
```

## Observações de produção

- Não usar o client secret que foi exposto.
- Não reiniciar Nginx sem antes executar `nginx -t`.
- Preferir `systemctl reload nginx` após validação.
- Validar endpoint público com `curl -I` e certificado com `openssl s_client` antes de alterações no Azure/Teams.
