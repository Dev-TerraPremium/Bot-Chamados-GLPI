# Deploy no Proxmox LXC

Este projeto foi ajustado para rodar em um LXC pequeno com Docker Compose, mantendo Redis, Ollama e a sessão do WhatsApp em volumes persistentes.

## Especificação recomendada

- Template: Ubuntu 24.04
- LXC: unprivileged marcado
- Nesting: marcado
- Disco: 30 GB
- CPU: 4 cores, ou 2 cores se for o limite disponível
- Memória: 6144 MB
- Swap: 2048 MB ou 4096 MB
- Rede: vmbr0

Mínimo para teste:

- Disco: 20 GB
- CPU: 2 cores
- Memória: 4096 MB
- Swap: 4096 MB

Com 4 GB de RAM a aplicação roda, mas a IA local pode responder devagar. Com 6 GB, `qwen2.5:1.5b` fica mais adequado para piloto.

## Instalação dentro do LXC

Execute como root no console do LXC:

```bash
apt update
apt install -y ca-certificates curl git
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
docker version
```

Clone ou atualize o projeto:

```bash
cd /opt
git clone <URL_DO_REPOSITORIO> Bot-Chamados-GLPI
cd /opt/Bot-Chamados-GLPI
```

Crie o arquivo de ambiente a partir do exemplo e preencha os tokens reais:

```bash
cp .env.docker.example .env.docker
nano .env.docker
```

Valores importantes para produção:

```bash
GLPI_INTEGRATION_MODE=real
CHANNEL_LINKING_MODE=redis
GLPI_DEFAULT_ENTITY_ID=3
GLPI_DEFAULT_REQUESTER_USER_ID=0
GLPI_ALLOW_INSECURE_HTTP=true
LOCAL_GENERATIVE_MODEL=qwen2.5:1.5b
ALLOWED_NUMBERS=66999990980
ALLOW_ALL_NUMBERS=false
```

Suba a aplicação:

```bash
ALLOWED_NUMBERS=66999990980 ALLOW_ALL_NUMBERS=false docker compose up -d --build
docker compose ps
```

Valide:

```bash
curl http://127.0.0.1:8000/health/runtime
curl http://127.0.0.1:8000/health/glpi
docker compose logs -f whatsapp
```

## Persistência

Os volumes abaixo não devem ser removidos em operação normal:

- `redis-data`: vínculos de autenticação e estado distribuído
- `ollama-data`: modelo local baixado
- `whatsapp-store`: sessão SQLite do WhatsApp

Para reiniciar sem perder login:

```bash
docker compose down
ALLOWED_NUMBERS=66999990980 ALLOW_ALL_NUMBERS=false docker compose up -d
```

Não use `docker compose down -v`, porque isso apaga os volumes e força novo QR/login.

## Limpeza de disco

Se o LXC chegar perto do limite de disco:

```bash
docker system prune -f
docker builder prune -f
```

Não use modelos maiores no LXC pequeno sem aumentar RAM e disco.
