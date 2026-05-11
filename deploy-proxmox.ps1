# =====================================================================
# deploy-proxmox.ps1 - Deploy do Bot-Chamados-GLPI no LXC Proxmox
# =====================================================================

param(
    [string]$Host    = "192.168.2.110",
    [int]   $Port    = 22,
    [string]$User    = "root",
    [string]$Pass    = "prEm@tErra26",
    [string]$RemoteDir = "/opt/bot-chamados-glpi",
    [string]$RepoUrl = "https://github.com/Dev-TerraPremium/Bot-Chamados-GLPI.git",
    [string]$LocalEnvDocker = "$PSScriptRoot\.env.docker"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step { param([string]$msg) Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok   { param([string]$msg) Write-Host "    [OK] $msg" -ForegroundColor Green }
function Write-Warn { param([string]$msg) Write-Host "    [!] $msg"  -ForegroundColor Yellow }

# ------------------------------------------------------------------
# 1. Garante Posh-SSH instalado
# ------------------------------------------------------------------
Write-Step "Verificando módulo Posh-SSH..."
if (-not (Get-Module -ListAvailable -Name Posh-SSH)) {
    Write-Warn "Posh-SSH não encontrado. Instalando (pode pedir confirmação)..."
    Install-Module -Name Posh-SSH -Scope CurrentUser -Force -AllowClobber
}
Import-Module Posh-SSH -Force
Write-Ok "Posh-SSH carregado."

# ------------------------------------------------------------------
# 2. Conecta ao LXC
# ------------------------------------------------------------------
Write-Step "Conectando a ${User}@${Host}:${Port}..."
$securePass = ConvertTo-SecureString $Pass -AsPlainText -Force
$cred       = New-Object System.Management.Automation.PSCredential ($User, $securePass)

$session = New-SSHSession -ComputerName $Host -Port $Port -Credential $cred `
    -AcceptKey -Force -ErrorAction Stop
Write-Ok "Sessão SSH estabelecida (Id=$($session.SessionId))."

function Run-Remote {
    param([string]$cmd, [switch]$IgnoreError)
    $result = Invoke-SSHCommand -SessionId $session.SessionId -Command $cmd -TimeOut 600
    if ($result.Output) { $result.Output | ForEach-Object { Write-Host "    $_" } }
    if ($result.ExitStatus -ne 0 -and -not $IgnoreError) {
        Write-Host "    [STDERR] $($result.Error)" -ForegroundColor Red
        throw "Comando falhou (exit $($result.ExitStatus)): $cmd"
    }
    return $result
}

# ------------------------------------------------------------------
# 3. Instala dependências no LXC
# ------------------------------------------------------------------
Write-Step "Atualizando apt e instalando dependências..."
Run-Remote "apt-get update -qq"
Run-Remote "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ca-certificates curl git fuse-overlayfs"
Write-Ok "Dependências instaladas."

# ------------------------------------------------------------------
# 4. Instala Docker se não existir
# ------------------------------------------------------------------
Write-Step "Verificando Docker..."
$dockerCheck = Invoke-SSHCommand -SessionId $session.SessionId -Command "docker version --format '{{.Server.Version}}' 2>/dev/null || echo NOT_FOUND"
if ($dockerCheck.Output -match "NOT_FOUND" -or $dockerCheck.ExitStatus -ne 0) {
    Write-Warn "Docker não encontrado. Instalando..."
    Run-Remote "curl -fsSL https://get.docker.com | sh"
    Run-Remote "systemctl enable --now docker"
    Write-Ok "Docker instalado."
} else {
    Write-Ok "Docker já instalado: $($dockerCheck.Output)"
}

# Configura storage-driver para LXC (fuse-overlayfs)
Write-Step "Configurando Docker daemon para LXC (fuse-overlayfs)..."
$daemonJson = @'
{
  "storage-driver": "fuse-overlayfs"
}
'@
Run-Remote "mkdir -p /etc/docker"
Run-Remote "echo '$daemonJson' > /etc/docker/daemon.json"
Run-Remote "systemctl restart docker"
Run-Remote "docker info --format '{{.Driver}}'"
Write-Ok "Storage driver configurado."

# ------------------------------------------------------------------
# 5. Clona ou atualiza o repositório
# ------------------------------------------------------------------
Write-Step "Clonando/atualizando repositório em $RemoteDir..."
$existsCheck = Invoke-SSHCommand -SessionId $session.SessionId -Command "test -d $RemoteDir/.git && echo EXISTS || echo NOT_EXISTS"
if ($existsCheck.Output -match "EXISTS") {
    Write-Warn "Repositório já existe. Fazendo git pull..."
    Run-Remote "cd $RemoteDir && git fetch --all && git reset --hard origin/main"
} else {
    Run-Remote "git clone $RepoUrl $RemoteDir"
}
Write-Ok "Repositório atualizado."

# ------------------------------------------------------------------
# 6. Copia o .env.docker de produção via SFTP
# ------------------------------------------------------------------
Write-Step "Enviando .env.docker de produção via SFTP..."
$sftp = New-SFTPSession -ComputerName $Host -Port $Port -Credential $cred -AcceptKey -Force
Set-SFTPFile -SessionId $sftp.SessionId -LocalFile $LocalEnvDocker -RemotePath "$RemoteDir/.env.docker" -Overwrite
Remove-SFTPSession -SessionId $sftp.SessionId | Out-Null
Write-Ok ".env.docker enviado."

# ------------------------------------------------------------------
# 7. Sobe a stack Docker Compose
# ------------------------------------------------------------------
Write-Step "Construindo e subindo containers (pode demorar na 1ª vez)..."
Write-Warn "O pull do modelo Ollama (qwen2.5:1.5b) vai acontecer dentro do container ollama-pull. Aguarde..."
Run-Remote "cd $RemoteDir && docker compose pull --ignore-pull-failures 2>&1 | tail -5" -IgnoreError
Run-Remote "cd $RemoteDir && docker compose up -d --build 2>&1"
Write-Ok "Stack iniciada."

# ------------------------------------------------------------------
# 8. Aguarda web ficar healthy
# ------------------------------------------------------------------
Write-Step "Aguardando serviço web ficar saudável (até 5 min)..."
$maxWait = 60   # tentativas
$waited  = 0
do {
    Start-Sleep -Seconds 5
    $waited++
    $status = Invoke-SSHCommand -SessionId $session.SessionId `
        -Command "docker inspect --format='{{.State.Health.Status}}' bot-chamados-web 2>/dev/null || echo pending"
    $s = ($status.Output -join "").Trim()
    Write-Host "    [$waited/60] web: $s"
    if ($s -eq "healthy") { break }
    if ($waited -ge $maxWait) {
        Write-Warn "Timeout aguardando web ficar healthy. Verificando logs..."
        Run-Remote "cd $RemoteDir && docker compose logs --tail=30 web" -IgnoreError
        break
    }
} while ($true)

# ------------------------------------------------------------------
# 9. Validação final
# ------------------------------------------------------------------
Write-Step "Validando endpoints de saúde..."
Run-Remote "curl -sf http://127.0.0.1:8000/health | python3 -m json.tool" -IgnoreError
Run-Remote "curl -sf http://127.0.0.1:8000/health/runtime | python3 -m json.tool" -IgnoreError
Run-Remote "curl -sf http://127.0.0.1:8000/health/glpi | python3 -m json.tool" -IgnoreError

Write-Step "Status dos containers:"
Run-Remote "cd $RemoteDir && docker compose ps"

Write-Step "Deploy concluído!"
Write-Host @"

╔══════════════════════════════════════════════════════╗
║  Bot-Chamados-GLPI rodando em http://192.168.2.110:8000  ║
║                                                      ║
║  Próximo passo: escanear QR do WhatsApp              ║
║  Execute: docker compose logs -f whatsapp            ║
║  (via SSH em 192.168.2.110)                          ║
╚══════════════════════════════════════════════════════╝
"@ -ForegroundColor Green

Remove-SSHSession -SessionId $session.SessionId | Out-Null
