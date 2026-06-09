# Autenticacao de Usuario e Vinculo de Canal

Este documento resume o mecanismo de identificacao do usuario no bot de chamados.

## Fluxo Atual

Quando um usuario entra em contato por um canal novo, como WhatsApp, Web Simulator ou Microsoft Teams:

1. O adaptador informa o identificador tecnico do canal.
2. O sistema verifica se ja existe um vinculo ativo para esse canal.
3. Se nao houver vinculo, o bot cria um registro `PENDING`.
4. O bot solicita apenas os 6 primeiros digitos do CPF.
5. O GLPI e consultado pelo prefixo do CPF.
6. O telefone do canal nao e comparado com telefones cadastrados no GLPI.

Resultados possiveis:

- Exatamente 1 usuario encontrado: o vinculo vira `ACTIVE` e o usuario segue para o menu.
- Nenhum usuario encontrado: o bot informa falha e permite nova tentativa ate o limite configurado.
- Mais de 1 usuario encontrado: o canal e bloqueado por seguranca e o usuario deve procurar o TI.

## Regra de Autenticacao

A autenticacao considera somente a correspondencia dos 6 primeiros digitos do CPF informado com o CPF localizado no GLPI.

O numero de telefone continua sendo usado apenas como identificador tecnico da conversa e chave de armazenamento do vinculo, mas nao participa da validacao de identidade.

## Componentes Principais

- `channel_linking_service.py`: controla estados `PENDING`, `ACTIVE` e `BLOCKED`.
- `document_partial_validator.py`: compara o prefixo do CPF e gera HMAC do CPF parcial.
- `glpi_user_identity_lookup_service.py`: busca usuarios ativos pelo prefixo do CPF no GLPI.
- `redis_channel_identity_link_store.py`: persiste vinculos no Redis quando o backend produtivo esta ativo.
- `channel_link_audit_service.py`: registra tentativas, falhas, bloqueios e criacao de vinculos.

## Configuracao

```env
CHANNEL_LINKING_MODE=mock
CHANNEL_LINK_CPF_PREFIX_LENGTH=6
CHANNEL_LINK_HMAC_PEPPER=changeme_in_production
CHANNEL_LINK_MAX_FAILED_ATTEMPTS=3
CHANNEL_LINK_ALLOW_WEB_SIMULATOR_AUTO_USER=true
CHANNEL_LINK_ACTIVE_TTL_SECONDS=0
CHANNEL_LINK_PENDING_TTL_SECONDS=900
CHANNEL_LINK_AUDIT_TTL_SECONDS=31536000
```

Para testar manualmente no Web Simulator, defina `CHANNEL_LINK_ALLOW_WEB_SIMULATOR_AUTO_USER=false`.

## Reset Seguro de Autenticacoes

Para invalidar vinculos antigos no Redis sem apagar dados de negocio, remova apenas chaves relacionadas a autenticacao e conversas ativas:

```bash
botctl redis reset-auth -y
```

Esse comando remove `channel_link:*` e `conversation:*`.

Se estiver usando o painel operacional, tambem e possivel remover um vinculo especifico:

```bash
botctl redis delete-link 66999990980
```

Use `botctl redis flush` apenas em ultimo caso, pois ele limpa todo o Redis, incluindo filas e estados temporarios nao relacionados ao vinculo.
