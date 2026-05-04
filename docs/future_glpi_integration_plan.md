# Plano futuro de integracao GLPI

- Implementar cliente REST real em `glpi_future_real_client.py`.
- Manter `glpi_client_interface.py` como contrato.
- Ajustar `glpi_ticket_payload_builder.py` aos campos reais do GLPI.
- Implementar sessao, renovacao e encerramento via `glpi_session_manager.py`.
- Mapear usuarios autenticados e vinculos de canal para usuarios GLPI.
- Mapear categorias internas para categorias GLPI reais.
- Nunca abrir ou alterar chamados via SQL direto.
- Usar banco somente para leitura controlada, diagnostico ou auditoria, quando permitido.

