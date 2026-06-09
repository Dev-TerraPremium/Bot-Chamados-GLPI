# Solicitação de Implementação: Menus Mais Diretos

Objetivo: implementar uma revisão de textos nos menus para deixá-los mais curtos, naturais e diretos, sem quebrar a lógica, os placeholders, a ordem das opções ou os fluxos existentes.

Contexto:
- a base atual já possui um editor de `.env` acessível pela interface `botctl`;
- ainda não existe uma função pronta para desabilitar menus diretamente pelo `botctl`;
- a implementação deve aproveitar essa base de configuração existente para encaixar a parametrização necessária;
- qualquer desativação de menu precisa continuar compatível com o fluxo atual e não pode quebrar o estado da conversa.
- a lógica de seleção de categoria continua funcionando normalmente; o que muda é só a exibição dessa informação para o usuário.

Regras:
- manter todos os placeholders exatamente como estão;
- manter os números e a semântica de cada opção;
- não remover caminhos de fluxo sem parametrização;
- não apagar nem alterar a funcionalidade de seleção de categoria, apenas ocultar sua apresentação ao usuário quando configurado;
- quando um menu puder ser desativado, a implementação deve ser feita por configuração no `.env` editável pelo `botctl`;
- o texto novo deve parecer uma mensagem curta para o usuário, sem floreio e sem quebra artificial de linhas;
- menus continuam sendo menus, com opções separadas por linha;
- textos explicativos podem ser encurtados, mas os blocos de escolha precisam continuar legíveis e estruturados.

Instruções para a IA que vai implementar:
1. Ler este documento inteiro antes de alterar o código.
2. Identificar as funções e pontos de renderização descritos em cada seção.
3. Atualizar os textos conforme o bloco `Depois`, preservando placeholders e comportamento.
4. Remover da interface qualquer exibição da categoria selecionada no fluxo de revisão, sem mexer na escolha interna da categoria.
5. Ocultar, via configuração em `.env`, qualquer menu ou caminho que já tenha sido marcado como opcional no documento, preservando a lógica interna.
6. Ajustar a documentação de operação se houver impacto no uso em produção.
7. Validar o resultado localmente antes de entregar.
8. Ao final, versionar corretamente as mudanças no GitHub e deixar o histórico coerente.
9. Após isso, preparar a aplicação para produção seguindo as instruções já existentes de deploy via SSH e registrar no código ou documentação qualquer passo novo necessário para o servidor.

Critério de aceite:
- o comportamento funcional permanece o mesmo, inclusive a seleção interna de categoria; apenas a exibição ao usuário muda nos trechos marcados;
- os menus ficam mais diretos sem perder clareza;
- a revisão do chamado não exibe mais a categoria selecionada para o usuário;
- a base fica pronta para parametrização futura por `.env`;
- a entrega final está versionada corretamente e pronta para deploy em produção via SSH conforme a documentação do projeto.

---

## 1) Menu principal

**Antes**

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

**Depois**

```text
👋 Olá, **{first_name}**!
Você entrou como **{login}** no Suporte TI - Terra Premium.

O que você quer fazer?

Digite o número:
1️⃣ **Abrir chamado**
2️⃣ **Consultar chamados**
3️⃣ **Complementar chamado**
4️⃣ **Encerrar atendimento**
```

**Variação somente abertura**

**Antes**

```text
👋 Olá, **{first_name}**!
Você está conectado como **{login}** no Suporte TI - Terra Premium.

Como posso ajudar agora?

Digite o número da opção desejada:
1️⃣ **Abrir um novo chamado**
2️⃣ **Encerrar atendimento**
```

**Depois**

```text
👋 Olá, **{first_name}**!
Você entrou como **{login}** no Suporte TI - Terra Premium.

O que você quer fazer?

Digite o número:
1️⃣ **Abrir chamado**
2️⃣ **Encerrar atendimento**
```

---

## 2) Menu de abertura de chamado

**Antes**

```text
📝 **Relato da Solicitação**

Descreva o que está acontecendo ou o que você precisa.

Se faltar algum detalhe, eu vou te perguntar em seguida.

Pode digitar sua descrição agora:
```

**Depois**

```text
Conte o que aconteceu ou o que você precisa, Se faltar alguma informação, eu peço depois.

Digite de maneira completa sua mensagem, descreva o máximo de detalhes:
```

---

## 3) Menu de classificação da demanda

**Antes**

```text
🛠️ **Classificação da Demanda**

Para direcionar sua solicitação ao técnico correto, selecione o tipo de atendimento:

1️⃣ **Estou com um problema** (Algo parou de funcionar ou está com erro)
2️⃣ **Preciso de algo novo** (Acessos, equipamentos ou novas instalações)

Digite o número correspondente:
```

**Depois**

```text
Escolha o tipo da sua solicitação:

1️⃣ **Estou com um problema** (algo parou de funcionar ou está com erro)
2️⃣ **Preciso de algo novo** (acesso, equipamento ou instalação)

Digite o número:
```

---

## 4) Menu “Meus chamados”

**Antes**

```text
📂 **Meus Chamados**

Como você deseja localizar seus tickets?

1️⃣ 🟢 **Chamados em aberto**
2️⃣ 🔵 **Chamados em atendimento**
3️⃣ 🕒 **Ver histórico recente**
4️⃣ 🔢 **Buscar por número (ID)**
5️⃣ ⬅️ **Voltar ao início**
```

**Depois**

```text
Veja seus chamados:

1️⃣ 🟢 **Em aberto**
2️⃣ 🔵 **Em atendimento**
3️⃣ 🕒 **Histórico recente**
4️⃣ 🔢 **Buscar por número**
5️⃣ ⬅️ **Voltar**
```

---

## 5) Mensagem de opção inválida

**Antes**

```text
⚠️ Não entendi a opção. Responda apenas com o **número** de uma das opções exibidas.
```

**Depois**

```text
⚠️ Opção inválida. Responda só com o número de uma das opções.
```

---

## 6) Menu de revisão da descrição

**Antes**

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

**Depois**

```text
Revise o texto do chamado:

📝 "{organized_text}"

Está certo?

1️⃣ **Sim, continuar**
2️⃣ **Quero ajustar**
3️⃣ **Usar texto original**
4️⃣ **Cancelar**
```

Observação: a categoria selecionada não deve mais ser exibida para o usuário em nenhum ponto desse fluxo. A seleção interna continua existindo e funcionando; apenas a exibição e a opção de troca ficam ocultas por configuração via `.env`.

---

## 7) Menu de localidade

**Antes**

```text
🏢 **Localidade do Chamado**

Informe a localidade que deve constar no chamado.

📍 **Exemplos:** Matriz, Rondonópolis

Digite a localidade abaixo:
```

**Depois**

```text
Informe a localidade do chamado, exemplo: Matriz, Rondonópolis.

Digite a localidade:
```

**Antes com retry**

```text
🏢 **Localidade do Chamado**

Não consegui localizar essa unidade no GLPI.

Informe novamente apenas a localidade que deve constar no chamado.

📍 **Exemplos:** Matriz, Rondonópolis

Digite a localidade abaixo:
```

**Depois com retry**

```text
Não encontrei essa unidade no GLPI, informe só a localidade novamente.

Exemplo: Matriz, Rondonópolis.

Digite a localidade:
```

**Antes com opções**

```text
🏢 **Localidade do Chamado**

Digite apenas o número da localidade:
1️⃣ {display_name}
2️⃣ {display_name}
...
```

**Depois com opções**

```text
Digite o número da localidade:

1️⃣ {display_name}
2️⃣ {display_name}
...
```

---

## 8) Menu de evidências

**Antes**

```text
📸 **Fotos e Evidências**

Você quer enviar fotos, prints ou documentos para ajudar na análise?

1️⃣ **Sim, enviar anexos**
2️⃣ **Não, seguir sem anexos**
```

**Depois**

```text
Quer enviar fotos, prints ou documentos?

1️⃣ **Sim**
2️⃣ **Não**
```

---

## 9) Menu de novo acompanhamento

**Antes**

```text
📝 **Novo Acompanhamento**

Veja como sua atualização será registrada no chamado:

💬 "{rewritten_text}"

Confirmar envio?

1️⃣ **Sim, adicionar ao chamado**
2️⃣ **Não, ajustar o texto**
3️⃣ **Cancelar**
```

**Depois**

```text
Veja o texto que será enviado:

💬 "{rewritten_text}"

Confirmar?

1️⃣ **Sim, enviar**
2️⃣ **Quero ajustar**
3️⃣ **Cancelar**
```

---

## 10) Catálogo de serviços

**Antes**

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

**Depois**

```text
Escolha uma categoria:

1️⃣ **Internet e rede**
2️⃣ **Computador ou notebook**
3️⃣ **Sistemas e ERP**
4️⃣ **Acessos e senhas**
5️⃣ **Impressoras e periféricos**
6️⃣ **E-mail e Microsoft 365**
7️⃣ **Outros assuntos**
8️⃣ **Buscar por nome**
9️⃣ **Voltar**
```

Observação: se algum menu/caminho de categoria for ocultado por configuração no `.env`, o texto também deve sumir da interface, sem quebrar o fluxo base nem a seleção interna.

---

## 11) Menu de nível de impacto

**Antes**

```text
🚦 **Nível de Impacto**

Como esse problema está afetando seu trabalho agora?

1️⃣ 🟢 Apenas uma dúvida ou pedido simples.
2️⃣ 🟡 Consigo trabalhar, mas com dificuldades.
3️⃣ 🟠 Não consigo trabalhar por causa disso.
4️⃣ 🔴 Afeta várias pessoas ou um setor inteiro.

Digite o número da opção:
```

**Depois**

```text
Como isso afeta seu trabalho?

1️⃣ 🟢 **Dúvida ou pedido simples**
2️⃣ 🟡 **Consigo trabalhar com dificuldade**
3️⃣ 🟠 **Não consigo trabalhar**
4️⃣ 🔴 **Afeta várias pessoas ou um setor**

Digite o número:
```

---

## 12) Catálogo interno de categorias

**Antes**

```text
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
```

**Depois**

```text
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
```

---

## 13) Catálogo interno de impacto

**Antes**

```text
1. **Dúvida ou solicitação simples**
2. **Afeta somente você, mas ainda consegue trabalhar**
3. **Afeta somente você e você não consegue trabalhar**
4. **Afeta várias pessoas**
5. **Afeta setor inteiro, filial ou operação crítica**
```

**Depois**

```text
1. **Dúvida ou pedido simples**
2. **Afeta só você, mas ainda dá para trabalhar**
3. **Afeta só você e impede o trabalho**
4. **Afeta várias pessoas**
5. **Afeta um setor, filial ou operação crítica**
```

Observação: o menu exibido ao usuário continua usando só as opções 1 a 4. A opção 5 permanece apenas na base interna.

---

## 14) Espaço para catálogo de mudanças futuras

**Antes**

```text
nome_do_menu:
versao_atual:
texto_original:
texto_novo_sugerido:
objetivo_da_mudanca:
observacoes_para_implementacao:
observacoes_para_revisao_humana:
```

**Depois**

```text
nome_do_menu:
versao_atual:
texto_antigo:
texto_novo:
motivo:
observacoes_tec:
observacoes_revisao:
```

---

## Notas de implementação

- O trecho que mostrava a categoria selecionada no fluxo de revisão deve ser removido da interface, mas a categoria continua sendo definida internamente pelo bot.
- Qualquer opção ou menu ocultado por configuração em `.env` deve desaparecer do texto exibido, sem alterar o contrato dos estados internos nem a seleção de categoria.
- Depois da implementação, a entrega precisa estar versionada no GitHub de forma consistente e pronta para publicação em produção via SSH, seguindo a documentação existente do projeto.
- Os textos novos foram pensados para reduzir quebra de linha, ruído visual e repetição.
