# Pasta reservada para integracao GLPI

Esta pasta isola tudo que futuramente conversara com o GLPI real. Nesta fase ela contem apenas interface, mock, builders e guardas de escopo.

## Objetivo

- Manter o motor conversacional independente do GLPI.
- Permitir trocar o mock por um cliente REST real sem duplicar regra de negocio por canal.
- Centralizar payloads, sessao, mapeamento de categoria e verificacoes de permissao.

## Implementacao futura

Os metodos de `glpi_client_interface.py` devem ser implementados por um cliente REST real:

- `init_session()`
- `kill_session()`
- `create_ticket(ticket_data)`
- `get_my_tickets(user_id)`
- `get_ticket_by_id(ticket_id, user_id)`
- `add_followup(ticket_id, user_id, content)`
- `find_user_by_identifier(identifier)`
- `find_category_by_name(category_name)`

`glpi_ticket_payload_builder.py` deve ser ajustado para o payload exato da API REST do GLPI usada no ambiente.

## Por que nao usar SQL direto para abrir chamado

A abertura, complemento e alteracao de chamados devem usar a API REST do GLPI. Escrita direta no banco contorna regras internas do GLPI, historico, permissoes, validacoes e pode corromper relacionamentos.

## Quando banco pode ser usado

Se existir acesso futuro ao banco, ele deve ser limitado a leitura controlada, diagnostico, auditoria e consultas tecnicas com escopo definido. Nunca deve receber SQL gerado por texto livre do usuario.

## Cuidados de seguranca

- Nao armazenar credenciais reais no codigo.
- Nao expor tokens em logs.
- Sempre validar escopo do usuario autenticado.
- Nunca permitir consulta ampla de chamados.
- Nunca usar texto do chat para montar SQL.
- Tratar integrações de canal como adaptadores, mantendo regras de negocio no motor central.

