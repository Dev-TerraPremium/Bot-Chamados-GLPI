# Catálogo dos Menus Originais

Este documento registra os textos originais dos menus que o robô envia no WhatsApp.

O objetivo aqui não é “explicar bonito” o fluxo. É servir como base de edição:
- você altera a comunicação dos menus aqui;
- outra IA usa este catálogo para implementar as mudanças no código;
- depois a gente revisa e ajusta de forma dinâmica.

Fonte principal do texto dos menus:
- [app/conversation_engine/conversation_messages.py](../../app/conversation_engine/conversation_messages.py)
- [app/triage_rules/category_catalog.py](../../app/triage_rules/category_catalog.py)
- [app/triage_rules/impact_catalog.py](../../app/triage_rules/impact_catalog.py)

## Como usar este arquivo

Para cada menu, mantenha:
- o texto original;
- o propósito do menu;
- os itens selecionáveis;
- um campo de observação livre para orientar a implementação.

Campos sugeridos para observação:
- `alterar_texto`: o que você quer mudar na comunicação;
- `manter_regra`: o que não pode mudar;
- `observacoes`: detalhes soltos para a outra IA;
- `prioridade`: o que deve ser tratado primeiro.

---

## 1) Menu principal

**Função:** menu inicial exibido após a autenticação do usuário.

**Arquivo de origem:** `build_main_menu()`

### Texto original

```text
👋 Olá, **{first_name}**!
Você está conectado como **{login}** no Suporte TI - Terra Premium.

Como posso ajudar agora?

Digite o número da opção desejada:
1️⃣ **Abrir um novo chamado**
2️⃣ **Consultar meus chamados**
3️⃣ **Complementar chamado existente**
4️⃣ **Encerrar atendimento**
```

### Variação de abertura

Quando o bot entra em modo somente abertura:

```text
👋 Olá, **{first_name}**!
Você está conectado como **{login}** no Suporte TI - Terra Premium.

Como posso ajudar agora?

Digite o número da opção desejada:
1️⃣ **Abrir um novo chamado**
2️⃣ **Encerrar atendimento**
```

### Observações para edição

```text
alterar_texto:
manter_regra:
observacoes:
prioridade:
```

---

## 2) Menu de abertura de chamado

**Função:** pede o relato inicial da solicitação.

**Arquivo de origem:** `build_open_ticket_prompt()`

### Texto original

```text
📝 **Relato da Solicitação**

Descreva o que está acontecendo ou o que você precisa.

Se faltar algum detalhe, eu vou te perguntar em seguida.

Pode digitar sua descrição agora:
```

### Observações para edição

```text
alterar_texto:
manter_regra:
observacoes:
prioridade:
```

---

## 3) Menu de classificação da demanda

**Função:** separa o chamado entre problema e solicitação.

**Arquivo de origem:** `build_ticket_type_prompt()`

### Texto original

```text
🛠️ **Classificação da Demanda**

Para direcionar sua solicitação ao técnico correto, selecione o tipo de atendimento:

1️⃣ **Estou com um problema** (Algo parou de funcionar ou está com erro)
2️⃣ **Preciso de algo novo** (Acessos, equipamentos ou novas instalações)

Digite o número correspondente:
```

### Observações para edição

```text
alterar_texto:
manter_regra:
observacoes:
prioridade:
```

---

## 4) Menu “Meus chamados”

**Função:** consulta e localização de tickets do usuário.

**Arquivo de origem:** `build_query_menu()`

### Texto original

```text
📂 **Meus Chamados**

Como você deseja localizar seus tickets?

1️⃣ 🟢 **Chamados em aberto**
2️⃣ 🔵 **Chamados em atendimento**
3️⃣ 🕒 **Ver histórico recente**
4️⃣ 🔢 **Buscar por número (ID)**
5️⃣ ⬅️ **Voltar ao início**
```

### Observações para edição

```text
alterar_texto:
manter_regra:
observacoes:
prioridade:
```

---

## 5) Mensagem de opção inválida

**Função:** resposta padrão quando o usuário digita algo fora do menu.

**Arquivo de origem:** `build_invalid_option_message()`

### Texto original

```text
⚠️ Não entendi a opção. Responda apenas com o **número** de uma das opções exibidas.
```

### Observações para edição

```text
alterar_texto:
manter_regra:
observacoes:
prioridade:
```

---

## 6) Menu de revisão da descrição

**Função:** confirma o texto organizado antes de seguir com a abertura ou complementação.

**Arquivo de origem:** `build_description_review_message()`

### Texto original

```text
👁️ **Revisão do Chamado**

Categoria definida para o chamado:
📂 **{category_name}**

Confira como sua solicitação será enviada ao técnico:

📝 "{organized_text}"

O texto reflete bem o seu problema?

1️⃣ **Sim, continuar**
2️⃣ **Não, quero ajustar o texto**
3️⃣ **Usar meu texto original**
4️⃣ **Cancelar**
```

### Observações para edição

```text
alterar_texto:
manter_regra:
observacoes:
prioridade:
```

---

## 7) Menu de localidade

**Função:** solicita a unidade/localidade do chamado.

**Arquivo de origem:** `build_location_prompt()`

### Texto original sem fallback

```text
🏢 **Localidade do Chamado**

Informe a localidade que deve constar no chamado.

📍 **Exemplos:** Matriz, Rondonópolis

Digite a localidade abaixo:
```

### Texto original com retry

```text
🏢 **Localidade do Chamado**

Não consegui localizar essa unidade no GLPI.

Informe novamente apenas a localidade que deve constar no chamado.

📍 **Exemplos:** Matriz, Rondonópolis

Digite a localidade abaixo:
```

### Texto original com opções

```text
🏢 **Localidade do Chamado**

Digite apenas o número da localidade:
1️⃣ {display_name}
2️⃣ {display_name}
...
```

### Observações para edição

```text
alterar_texto:
manter_regra:
observacoes:
prioridade:
```

---

## 8) Menu de evidências

**Função:** pergunta se o usuário quer enviar anexos.

**Arquivo de origem:** `build_evidence_question()`

### Texto original

```text
📸 **Fotos e Evidências**

Você quer enviar fotos, prints ou documentos para ajudar na análise?

1️⃣ **Sim, enviar anexos**
2️⃣ **Não, seguir sem anexos**
```

### Observações para edição

```text
alterar_texto:
manter_regra:
observacoes:
prioridade:
```

---

## 9) Menu de novo acompanhamento

**Função:** confirma o texto antes de adicionar uma atualização ao chamado.

**Arquivo de origem:** `build_complement_review_message()`

### Texto original

```text
📝 **Novo Acompanhamento**

Veja como sua atualização será registrada no chamado:

💬 "{rewritten_text}"

Confirmar envio?

1️⃣ **Sim, adicionar ao chamado**
2️⃣ **Não, ajustar o texto**
3️⃣ **Cancelar**
```

### Observações para edição

```text
alterar_texto:
manter_regra:
observacoes:
prioridade:
```

---

## 10) Catálogo de serviços

**Função:** catálogo principal de categorias para abertura detalhada.

**Arquivo de origem:** `render_category_menu()`

### Texto original

```text
📚 **Catálogo de Serviços**

Selecione a categoria que melhor descreve sua necessidade:
1️⃣ **Internet e Conectividade**
2️⃣ **Computador ou Notebook**
3️⃣ **Sistemas e ERP**
4️⃣ **Acessos e Senhas**
5️⃣ **Impressoras e Periféricos**
6️⃣ **E-mail e Microsoft 365**
7️⃣ **Outros Assuntos**
8️⃣ **🔍 Pesquisar por nome**
9️⃣ **⬅️ Voltar**
```

### Observações para edição

```text
alterar_texto:
manter_regra:
observacoes:
prioridade:
```

---

## 11) Menu de nível de impacto

**Função:** mede o impacto do problema no trabalho do usuário.

**Arquivo de origem:** `render_impact_menu()`

### Texto original

```text
🚦 **Nível de Impacto**

Como esse problema está afetando seu trabalho agora?

1️⃣ 🟢 Apenas uma dúvida ou pedido simples.
2️⃣ 🟡 Consigo trabalhar, mas com dificuldades.
3️⃣ 🟠 Não consigo trabalhar por causa disso.
4️⃣ 🔴 Afeta várias pessoas ou um setor inteiro.

Digite o número da opção:
```

### Observações para edição

```text
alterar_texto:
manter_regra:
observacoes:
prioridade:
```

---

## 12) Catálogo interno de categorias

**Função:** base real das categorias usadas no fluxo detalhado.

**Arquivo de origem:** `CATEGORY_OPTIONS` em `category_catalog.py`

### Lista original

1. **Internet / Rede**
   - descrição: problema de rede ou internet
   - exemplos: “Estou sem internet.”, “A rede está oscilando.”, “Não acesso a VPN.”

2. **Computador / Notebook**
   - descrição: problema no computador ou notebook
   - exemplos: “Notebook não liga.”, “Computador está lento.”, “Tela está piscando.”

3. **Impressora**
   - descrição: problema de impressão
   - exemplos: “Não consigo imprimir.”, “Impressora está atolando papel.”, “Fila travada.”

4. **Sistema / ERP**
   - descrição: problema no sistema ou ERP
   - exemplos: “ERP travando.”, “Sistema apresenta erro ao salvar.”, “Tela não carrega.”

5. **E-mail / Microsoft 365**
   - descrição: problema de e-mail ou Microsoft 365
   - exemplos: “E-mail não abre.”, “Outlook não sincroniza.”, “Teams não entra.”

6. **Acesso / Senha**
   - descrição: problema ou solicitação de acesso
   - exemplos: “Esqueci minha senha do ERP.”, “Meu usuário do Windows está bloqueado.”, “Preciso de acesso à pasta Financeiro.”, “Preciso alterar a permissão de um colaborador.”, “MFA não está funcionando.”

7. **Telefonia**
   - descrição: problema de telefonia
   - exemplos: “Ramal sem linha.”, “Telefone mudo.”, “Não consigo transferir ligação.”

8. **GLPI**
   - descrição: problema relacionado ao GLPI
   - exemplos: “GLPI não abre.”, “Não consigo consultar chamado.”, “Erro ao fechar chamado.”

9. **Solicitação de equipamento**
   - descrição: equipamento solicitado
   - exemplos: “Preciso de mouse.”, “Solicito um monitor.”, “Novo colaborador precisa de kit.”

10. **Câmeras / CFTV**
    - descrição: problema de câmeras ou CFTV
    - exemplos: “Câmera sem imagem.”, “DVR offline.”, “Imagem travando.”

11. **Ubiquiti / Wi-Fi**
    - descrição: problema de Wi-Fi ou Ubiquiti
    - exemplos: “Wi-Fi caindo.”, “Access point offline.”, “Sinal fraco no depósito.”

12. **Outro**
    - descrição: solicitação diferente
    - exemplos: “Tenho uma solicitação diferente.”

### Observações para edição

```text
alterar_texto:
manter_regra:
observacoes:
prioridade:
```

---

## 13) Catálogo interno de impacto

**Função:** base real das opções de impacto.

**Arquivo de origem:** `IMPACT_OPTIONS` em `impact_catalog.py`

### Lista original

1. **Dúvida ou solicitação simples**
2. **Afeta somente você, mas ainda consegue trabalhar**
3. **Afeta somente você e você não consegue trabalhar**
4. **Afeta várias pessoas**
5. **Afeta setor inteiro, filial ou operação crítica**

### Observação

O menu exibido ao usuário usa apenas as opções 1 a 4. A opção 5 existe na base interna, mas não aparece no texto atual do menu.

### Observações para edição

```text
alterar_texto:
manter_regra:
observacoes:
prioridade:
```

---

## 14) Espaço para catálogo de mudanças futuras

Use este bloco para registrar novas versões sem perder o histórico.

```text
nome_do_menu:
versao_atual:
texto_original:
texto_novo_sugerido:
objetivo_da_mudanca:
observacoes_para_implementacao:
observacoes_para_revisao_humana:
```

