# Autenticação de Usuário e Vínculo de Canal

Este documento detalha o mecanismo de **Vínculo de Identidade por Canal**, implementado para autenticar os usuários no *Assistente de Chamados TI On-Premise* de forma segura, mantendo a experiência conversacional e sem exigir login/senha via chat.

## 1. Como o vínculo funciona (Fluxo de Negócio)

Quando um usuário entra em contato pelo bot em um novo canal (ex: WhatsApp, Web Simulator):
1. O adaptador fornece um identificador (ex: telefone `66999990980`).
2. O sistema verifica se existe um vínculo ativo para este telefone.
3. Se **não houver** vínculo:
   - O bot cria um vínculo `PENDING`.
   - O bot responde: *"Identifiquei o telefone final 0980. Informe os 4 primeiros dígitos do seu CPF."*
4. O usuário responde com os dígitos numéricos.
5. O bot **normaliza** o CPF parcial (removendo pontuações) e consulta os usuários do GLPI:
   - Cruza o número de telefone do canal (normalizado) com os telefones do usuário GLPI (`phone`, `phone2`, `mobile`).
   - Verifica se o CPF cadastrado no GLPI (`registration_number`) começa exatamente com os dígitos informados.
6. Resultados possíveis:
   - **Exatamente 1 usuário (Sucesso):** Cria o vínculo definitivo (`ACTIVE`), avisa o usuário pelo nome e salva o *hash* do CPF parcial via HMAC-SHA256. A partir daqui, o usuário usa o bot sem precisar informar CPF novamente.
   - **0 usuários (Falha):** Informa o erro. Após 3 tentativas falhas (`CHANNEL_LINK_MAX_FAILED_ATTEMPTS`), bloqueia o canal temporariamente.
   - **Mais de 1 usuário (Ambiguidade):** Bloqueia imediatamente o canal por segurança e orienta o usuário a buscar o TI.

## 2. Componentes Criados/Modificados

Os seguintes componentes foram adicionados à pasta `app/authentication_and_identity/`:

### Módulos Principais
- **`channel_identity_link_model.py`**: Modelagem do estado e da entidade do vínculo (com campos como `status`, `glpi_user_id`, `failed_attempts`, etc.).
- **`channel_linking_service.py`**: Coração do sistema. Implementa a lógica listada acima, incluindo o tratamento de tentativas e transições de estado.
- **`channel_identifier_normalizer.py`**: Normaliza telefones (removendo `+55`, espaços, pontuações) e CPFs. Responsável também por aplicar as máscaras usadas nos logs de auditoria (`******0980`).
- **`document_partial_validator.py`**: Compara o CPF e faz o *hashing* seguro via `HMAC-SHA256` utilizando um pepper (variável de ambiente).
- **`glpi_user_identity_lookup_service.py`**: Serviço que consulta e cruza dados do telefone com o CPF prefixo (implementação Mock atual preparada para adoção de API REST no futuro).
- **`admin_channel_unlock_service.py`**: Métodos para a administração desbloquear, bloquear ou revogar vínculos.
- **`channel_link_audit_service.py`**: Criação do rastro de auditoria (`logs` estruturados persistidos no Redis) sempre que um canal é validado, bloqueado, falha no CPF ou sofre ambiguidade.

### Integração com o Motor
- **`conversation_flow_controller.py`**: Atualizado para interceptar a conversa na camada mais alta, encaminhando-a para o serviço de vínculo **antes** da criação do contexto do menu principal. O contexto (`ConversationContext`) só é carregado e populado se o vínculo for `ACTIVE`.

## 3. Configurações (`.env`)

Novas configurações foram adicionadas e são mandatórias:

```env
CHANNEL_LINKING_MODE=mock
CHANNEL_LINK_CPF_PREFIX_LENGTH=4
CHANNEL_LINK_HMAC_PEPPER=changeme_in_production
CHANNEL_LINK_MAX_FAILED_ATTEMPTS=3
CHANNEL_LINK_ALLOW_WEB_SIMULATOR_AUTO_USER=true
CHANNEL_LINK_ACTIVE_TTL_SECONDS=0
CHANNEL_LINK_PENDING_TTL_SECONDS=900
CHANNEL_LINK_AUDIT_TTL_SECONDS=31536000
```

> **NOTA:** Quando testar pelo Web Simulator, se a variável `CHANNEL_LINK_ALLOW_WEB_SIMULATOR_AUTO_USER=true`, ele passará automaticamente a validação (usando um usuário mock). Para testar a experiência real de colocar o CPF no Web Simulator, altere este valor para `false`.

## 4. Testes e Validações

O Python e a biblioteca `pytest` foram instalados e todos os testes desenhados rodaram com sucesso (`100% passed`).

Os seguintes testes unitários em `tests/test_channel_linking.py` confirmam a lógica:
1. **`test_normalize_phone` / `test_normalize_cpf`**: Garante remoção de máscaras e country codes.
2. **`test_cpf_partial_validation_match`**: Testa se os primeiros 4 dígitos batem corretamente.
3. **`test_link_success_flow`**: Testa a jornada completa de receber um *Oi*, receber a mensagem pedindo o CPF, informar o CPF e na sequência verificar se o usuário autênticado foi populado no contexto.
4. **`test_link_ambiguity_flow`**: Valida a colisão de 2 usuários com o mesmo telefone e CPF parcial que ativa o status de bloqueio.
5. **`test_link_failure_and_block_flow`**: Valida as 3 tentativas e o posterior bloqueio com log de auditoria.

## 5. Como Testar (Sem Docker)

Uma vez que você não tem o Docker, pode validar tudo rodando o bot localmente através da memória.

1. **Dependências em seu ambiente Python:**
   A inteligência artificial que for testar pode executar os comandos listados no README:
   ```bash
   pip install -r requirements.txt
   ```
2. **Rodar o servidor local (Memória + Mock GLPI):**
   ```bash
   uvicorn app.main:app --reload
   ```
3. **Abrir no navegador:**
   - Acesse `http://localhost:8000`
4. **Desabilitar Auto-Login no Simulador:**
   - No arquivo `.env.local` (ou equivalente), ajuste `CHANNEL_LINK_ALLOW_WEB_SIMULATOR_AUTO_USER=false`. Isso fará com que o Web Simulator seja interceptado e caia na verificação de CPF com o telefone genérico Mock configurado.

O código já foi construído, refatorado, e testado nativamente no projeto usando o interpretador local. As proteções do fluxo da conversa, juntamente com o modelo em Redis, suportam o novo processo produtivo com segurança.
