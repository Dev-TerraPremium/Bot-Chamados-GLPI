# Estrategia de IA generativa local

O MVP usa uma camada generativa local para organizar descricoes em portugues do Brasil.

## Modelo padrao

- Runtime: Ollama local
- Modelo: `qwen2.5:1.5b`
- Licenca do modelo Qwen: Apache 2.0
- Uso: somente organizacao de descricoes e complementos de chamados

## Funcao unica

A IA local recebe o texto do usuario e deve retornar JSON estruturado com:

- `status`: `organized` ou `needs_clarification`
- `organized_text`: texto curto organizado
- `clarification_question`: pergunta curta quando a entrada estiver confusa
- `confidence`: confianca numerica entre 0 e 1

Ela nao classifica categoria, nao define gravidade, nao sugere causa, nao gera diagnostico e nao conversa livremente.

## Parametros

- `LOCAL_LIGHT_AI_MODE=generative_ollama`
- `OLLAMA_BASE_URL=http://127.0.0.1:11434`
- `LOCAL_GENERATIVE_MODEL=qwen2.5:1.5b`
- `LOCAL_GENERATIVE_TIMEOUT_SECONDS=30`

## Preparacao local

```bash
ollama pull qwen2.5:1.5b
```

O projeto nao usa fallback de regex para organizacao de descricao. Se o runtime local nao estiver disponivel, o bot informa indisponibilidade da IA generativa local.
