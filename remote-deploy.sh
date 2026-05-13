#!/bin/bash
# =====================================================================
# remote-deploy.sh — Executado DENTRO do LXC (root@192.168.2.110)
# =====================================================================
set -euo pipefail

REMOTE_DIR="/opt/bot-chamados-glpi"
REPO_URL="https://github.com/Dev-TerraPremium/Bot-Chamados-GLPI.git"

log()  { echo -e "\n\033[36m==> $*\033[0m"; }
ok()   { echo -e "\033[32m    [OK] $*\033[0m"; }
warn() { echo -e "\033[33m    [!]  $*\033[0m"; }

# ------------------------------------------------------------------
# 1. Dependências base
# ------------------------------------------------------------------
log "Atualizando apt e instalando dependências..."
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    ca-certificates curl git fuse-overlayfs uidmap
ok "Dependências instaladas."

# ------------------------------------------------------------------
# 2. Docker
# ------------------------------------------------------------------
log "Verificando Docker..."
if ! command -v docker &>/dev/null; then
    warn "Docker não encontrado. Instalando..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    ok "Docker instalado."
else
    ok "Docker já presente: $(docker --version)"
fi

# Configura storage driver para LXC unprivileged
log "Verificando storage driver..."
ok "Storage driver ativo: $(docker info --format '{{.Driver}}')"

# ------------------------------------------------------------------
# 3. Repositório
# ------------------------------------------------------------------
log "Confirmando diretório do projeto em $REMOTE_DIR..."
cd "$REMOTE_DIR"
ok "Código fonte pronto."

# ------------------------------------------------------------------
# 4. .env.docker já foi copiado via SCP antes deste script rodar
#    Confirma existência
# ------------------------------------------------------------------
log "Verificando .env.docker..."
if [ ! -f "$REMOTE_DIR/.env.docker" ]; then
    echo "ERRO: .env.docker não encontrado em $REMOTE_DIR/.env.docker"
    exit 1
fi
ok ".env.docker presente."

OLLAMA_ENABLED="$(awk -F= '/^LOCAL_OLLAMA_ENABLED=/{print tolower($2)}' "$REMOTE_DIR/.env.docker" | tail -n 1)"
if [ -z "$OLLAMA_ENABLED" ]; then
    OLLAMA_ENABLED="true"
fi

COMPOSE_SERVICES=(redis web worker-ai worker-glpi whatsapp)
if [[ "$OLLAMA_ENABLED" =~ ^(1|true|yes|sim|on)$ ]]; then
    COMPOSE_SERVICES+=(ollama ollama-pull)
    ok "Runtime Ollama habilitado para este deploy."
else
    warn "Runtime Ollama desabilitado; deploy usara somente a IA via API."
    docker compose stop ollama ollama-pull >/dev/null 2>&1 || true
    docker compose rm -f ollama ollama-pull >/dev/null 2>&1 || true
fi

log "Instalando painel terminal botctl..."
if [ -f "$REMOTE_DIR/scripts/botctl.py" ]; then
    python3 - <<'PY'
from pathlib import Path

path = Path("/opt/bot-chamados-glpi/scripts/botctl.py")
data = path.read_bytes()
path.write_bytes(data.replace(b"\r\n", b"\n").replace(b"\r", b"\n"))
PY
    chmod +x "$REMOTE_DIR/scripts/botctl.py"
    ln -sf "$REMOTE_DIR/scripts/botctl.py" /usr/local/bin/botctl
    ok "botctl instalado. Use: botctl"
else
    warn "scripts/botctl.py nao encontrado; pulando instalacao do botctl."
fi

# Garante ALLOWED_NUMBERS correto
if ! grep -q "ALLOWED_NUMBERS=66999990980" "$REMOTE_DIR/.env.docker"; then
    warn "ALLOWED_NUMBERS não encontrado ou diferente — corrigindo..."
    sed -i 's/^ALLOWED_NUMBERS=.*/ALLOWED_NUMBERS=66999990980/' "$REMOTE_DIR/.env.docker"
fi
ok "ALLOWED_NUMBERS=66999990980 confirmado."

# ------------------------------------------------------------------
# 5. Build e subida
# ------------------------------------------------------------------
cd "$REMOTE_DIR"
log "Build e subida dos containers (primeira vez pode demorar 5-15min)..."
DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 docker compose up -d --build "${COMPOSE_SERVICES[@]}"
ok "Containers iniciados."

# ------------------------------------------------------------------
# 6. Status
# ------------------------------------------------------------------
log "Status dos containers:"
docker compose ps

log "Aguardando web ficar healthy (até 6 min)..."
for i in $(seq 1 72); do
    STATUS=$(docker inspect --format='{{.State.Health.Status}}' bot-chamados-web 2>/dev/null || echo "pending")
    echo "    [$i/72] web: $STATUS"
    [ "$STATUS" = "healthy" ] && break
    sleep 5
done

log "Health checks:"
curl -sf http://127.0.0.1:8000/health       | python3 -m json.tool 2>/dev/null || echo "(ainda subindo)"
curl -sf http://127.0.0.1:8000/health/glpi  | python3 -m json.tool 2>/dev/null || echo "(ainda subindo)"

echo ""
echo "============================================================"
echo " Deploy concluído! IP: 192.168.2.110:8000"
echo " Painel terminal no LXC:"
echo "   botctl"
echo "   botctl status"
echo "   botctl logs whatsapp -f"
echo " Para ver o QR do WhatsApp:"
echo "   docker compose -f $REMOTE_DIR/compose.yml logs -f whatsapp"
echo "============================================================"
