param(
    [string]$AllowedNumbers = "66999990980",
    [string]$UbuntuDistro = "Ubuntu-24.04",
    [string]$ProjectLinuxPath = "/mnt/c/projects/Bot-Chamados-GLPI",
    [string]$ApiUrl = "http://127.0.0.1:8000/api/conversation/message",
    [switch]$Status,
    [switch]$Stop,
    [switch]$Logs,
    [switch]$SkipWhatsApp
)

$ErrorActionPreference = "Stop"
$KeepAlivePidFile = Join-Path $env:TEMP "bot-chamados-wsl-keepalive.pid"

function Invoke-Ubuntu {
    param([string]$Command)
    wsl -d $UbuntuDistro -u root sh -lc $Command
}

function ConvertTo-ShellSingleQuoted {
    param([string]$Value)
    return "'" + ($Value -replace "'", "'\''") + "'"
}

function Wait-HttpOk {
    param([string]$Url, [int]$Seconds = 90)
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -eq 200) {
                return
            }
        } catch {
            Start-Sleep -Seconds 2
        }
    } while ((Get-Date) -lt $deadline)
    throw "API nao ficou saudavel em $Seconds segundos: $Url"
}

if ($Status) {
    Invoke-Ubuntu "cd '$ProjectLinuxPath' && docker compose ps && docker ps"
    exit 0
}

if ($Logs) {
    Invoke-Ubuntu "cd '$ProjectLinuxPath' && docker compose logs --tail=200 -f"
    exit 0
}

if ($Stop) {
    Invoke-Ubuntu "cd '$ProjectLinuxPath' && docker compose down"
    if (Test-Path $KeepAlivePidFile) {
        $keepAlivePid = Get-Content $KeepAlivePidFile -ErrorAction SilentlyContinue
        if ($keepAlivePid) {
            Stop-Process -Id ([int]$keepAlivePid) -ErrorAction SilentlyContinue
        }
        Remove-Item $KeepAlivePidFile -ErrorAction SilentlyContinue
    }
    Write-Host "Aplicacao encerrada."
    exit 0
}

if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    throw "WSL nao encontrado no Windows."
}

if ([string]::IsNullOrWhiteSpace($AllowedNumbers)) {
    throw "AllowedNumbers esta vazio. Por seguranca, informe pelo menos um numero ou edite este script conscientemente."
}

Write-Host "[1/4] Mantendo Ubuntu/WSL ativo..."
$shouldStartKeepAlive = $true
if (Test-Path $KeepAlivePidFile) {
    $existingPid = Get-Content $KeepAlivePidFile -ErrorAction SilentlyContinue
    if ($existingPid -and (Get-Process -Id ([int]$existingPid) -ErrorAction SilentlyContinue)) {
        $shouldStartKeepAlive = $false
    }
}
if ($shouldStartKeepAlive) {
    $keepAlive = Start-Process -FilePath "wsl.exe" -ArgumentList @(
        "-d", $UbuntuDistro,
        "-u", "root",
        "--exec", "sleep", "infinity"
    ) -WindowStyle Hidden -PassThru
    Set-Content -Path $KeepAlivePidFile -Value $keepAlive.Id
    Start-Sleep -Seconds 3
}

$logIgnored = if ([string]::IsNullOrWhiteSpace($env:LOG_IGNORED_MESSAGES)) { "false" } else { $env:LOG_IGNORED_MESSAGES }
$allowedShell = ConvertTo-ShellSingleQuoted $AllowedNumbers
$logShell = ConvertTo-ShellSingleQuoted $logIgnored
$services = if ($SkipWhatsApp) { "redis ollama ollama-pull web worker-ai worker-glpi" } else { "" }

Write-Host "[2/4] Subindo Docker Compose dentro do Ubuntu..."
Invoke-Ubuntu "systemctl start docker >/dev/null 2>&1 || service docker start >/dev/null 2>&1 || true; cd '$ProjectLinuxPath' && ALLOWED_NUMBERS=$allowedShell ALLOW_ALL_NUMBERS=false LOG_IGNORED_MESSAGES=$logShell docker compose up -d $services"

Write-Host "[3/4] Aguardando API FastAPI..."
Wait-HttpOk -Url "http://127.0.0.1:8000/health" -Seconds 120

if ($SkipWhatsApp) {
    Write-Host "Docker/API online. WhatsApp nao foi iniciado por opcao."
    exit 0
}

Write-Host "[4/4] Conferindo conector WhatsApp dockerizado com sandbox ativo..."
Write-Host "Numeros permitidos: $AllowedNumbers"
Invoke-Ubuntu "cd '$ProjectLinuxPath' && docker compose ps whatsapp && docker compose logs --tail=80 whatsapp"
