#!/usr/bin/env python3
"""
Terminal control panel for Bot-Chamados-GLPI.

Designed to run inside the Proxmox LXC where the Docker Compose stack lives.
It intentionally uses only the Python standard library plus system commands.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Iterable
from urllib.error import URLError
from urllib.request import urlopen


PROJECT_DIR = Path(os.getenv("BOTCTL_PROJECT_DIR", "/opt/bot-chamados-glpi"))
ENV_FILE = PROJECT_DIR / ".env.docker"
COMPOSE_FILE = PROJECT_DIR / "compose.yml"
DEFAULT_HEALTH_URL = "http://127.0.0.1:8000"
SERVICES = ("web", "whatsapp", "worker-ai", "worker-glpi", "redis", "ollama")
SECRET_NAMES = ("TOKEN", "PASSWORD", "PASS", "SECRET", "PEPPER")

CONFIG_MANUAL = {
    "Sistema e Ambiente": {
        "APP_ENV": "Ambiente de execução: 'production' ativa validações críticas, 'local' ou 'dev' relaxam restrições.",
        "APP_NAME": "Nome do bot exibido no cabeçalho e nas mensagens de boas vindas.",
        "EXPOSE_DEBUG_ROUTES": "Habilita rotas administrativas /health, /docs e simulações de tela (WebUI).",
    },
    "Integracao GLPI": {
        "GLPI_INTEGRATION_MODE": "Modo de operação: 'real' (conecta na API) ou 'mock' (simula operações sem alterar o GLPI).",
        "GLPI_BASE_URL": "URL base da API do GLPI (deve terminar em /apirest.php).",
        "GLPI_APP_TOKEN": "App-Token da API habilitada nas configurações do GLPI.",
        "GLPI_USER_TOKEN": "Token pessoal da conta que o bot usará para registrar chamados no GLPI.",
        "GLPI_DEFAULT_ENTITY_ID": "ID da Entidade raiz/destino para novos usuários e tickets no GLPI.",
        "GLPI_DEFAULT_PROFILE_ID": "ID do Perfil padrão para acesso (Self-Service / Requerente).",
        "GLPI_TICKET_PUBLIC_URL_TEMPLATE": "Template de URL para criar links clicáveis do ticket (ex: https://url.com/index.php?redirect=ticket_{id}).",
    },
    "Inteligencia Artificial & Triage": {
        "LOCAL_LIGHT_AI_MODE": "Provedor de IA: 'generative_google' (Gemini - nuvem) ou 'generative_ollama' (Processamento Local).",
        "GOOGLE_AI_API_KEY": "Chave de API da Google para rodar o modelo Gemini (Gratuito/Pago dependendo da cota).",
        "LOCAL_OLLAMA_ENABLED": "Ativa/Desativa o container Ollama local no Docker (consome muita CPU/RAM se ligado).",
        "AI_GUIDED_DETAILING_ENABLED": "Habilita a IA a fazer perguntas dinâmicas de acompanhamento para enriquecer o relato.",
        "AI_MAX_CLARIFICATION_QUESTIONS": "Limite máximo de perguntas que o robô fará antes de aceitar a descrição final.",
        "AI_MAX_INPUT_CHARS": "Proteção de contexto da IA: trunca o input do usuário se passar deste tamanho.",
    },
    "Seguranca & Autenticacao": {
        "CHANNEL_LINKING_MODE": "Define como vincular WhatsApp e Login: 'real' busca CPF no GLPI, 'mock' aceita dados genéricos.",
        "CHANNEL_LINK_HMAC_PEPPER": "String secreta única para embaralhar o hash de autenticação dos celulares.",
        "ALLOWED_NUMBERS": "Filtro de firewall: Apenas estes números com DDD separados por vírgula conseguem falar com o bot.",
        "ALLOW_ALL_NUMBERS": "Desliga o firewall de números se 'true', permitindo uso corporativo irrestrito.",
    },
    "Infraestrutura (Redis/Celery)": {
        "STATE_BACKEND": "Onde guardar o estado da conversa: 'redis' (ideal produção) ou 'memory' (não escala).",
        "USE_CELERY_WORKERS": "Processamento em segundo plano das mensagens, melhora a estabilidade da API (obrigatório em prod).",
        "REDIS_URL": "Endpoint principal de cache e sessões ativas dos usuários.",
        "AI_QUEUE_NAME": "Nome da fila de processamento exclusivo para demandas da Inteligência Artificial.",
    },
    "Notificacoes Ativas": {
        "TICKET_NOTIFICATIONS_ENABLED": "Habilita o Worker que monitora mudanças no GLPI e avisa o usuário no WhatsApp.",
        "TICKET_NOTIFICATION_POLL_INTERVAL_SECONDS": "De quanto em quanto tempo o bot consulta mudanças no banco/API do GLPI.",
        "WHATSAPP_INTERNAL_API_TOKEN": "Chave de autenticação interna que permite ao backend web enviar mensagens usando o container do Go.",
    }
}

try:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (AttributeError, ValueError):
    pass


def c(text: str, color: str) -> str:
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "cyan": "\033[96m",
        "white": "\033[97m",
        "bold": "\033[1m",
        "dim": "\033[2m",
        "underline": "\033[4m",
        "invert": "\033[7m",
        "bg_blue": "\033[44m",
        "reset": "\033[0m",
    }
    if not sys.stdout.isatty():
        return str(text)
    parts = color.split("+")
    prefix = "".join(colors.get(p.strip(), "") for p in parts)
    return f"{prefix}{text}{colors['reset']}"


def header(text: str) -> None:
    w = 60
    print("\n" + c("┌" + "─"*(w-2) + "┐", "cyan+dim"))
    print(c("│", "cyan+dim") + c(f" {text} ".center(w-2), "cyan+bold") + c("│", "cyan+dim"))
    print(c("└" + "─"*(w-2) + "┘", "cyan+dim"))


def banner() -> None:
    art = r"""
    ____        __  ______ ______ __ 
   / __ )____  / /_/ ____//_  __// / 
  / __  / __ \/ __/ /      / /  / /  
 / /_/ / /_/ / /_/ /___   / /  / /___
/_____/\____/\__/\____/  /_/  /_____/
    """
    print(c(art, "cyan+bold"))
    print(c("  » ASSISTENTE DE CHAMADOS GLPI V3 «  ", "cyan+invert").center(44))
    print(c("  Terminal de Controle Corporativo    ", "dim").center(44) + "\n")


def clear_screen() -> None:
    os.system('cls' if os.name == 'nt' else 'clear')


def info(text: str) -> None:
    print(f"{c('[i]', 'cyan')} {text}", flush=True)


def ok(text: str) -> None:
    print(f"{c('[+]', 'green')} {c(text, 'green')}", flush=True)


def warn(text: str) -> None:
    print(f"{c('[!]', 'yellow')} {c(text, 'yellow')}", flush=True)


def fail(text: str, code: int = 1) -> None:
    print(f"{c('[x]', 'red')} {c(text, 'red+bold')}", file=sys.stderr)
    raise SystemExit(code)


def print_table(headers_list: list[str], rows: list[list[str]], widths: list[int] | None = None) -> None:
    if not rows:
        return
    if not widths:
        widths = [max(len(str(item)) for item in col) for col in zip(headers_list, *rows)]
    
    sep = " " + " │ ".join("─" * w for w in widths) + " "
    
    # Header
    header_str = " │ ".join(c(str(h).ljust(w), "white+bold") for h, w in zip(headers_list, widths))
    print(" " + header_str)
    print(c(sep, "dim"))
    
    # Body
    for row in rows:
        colored_row = []
        for val, w in zip(row, widths):
            clean_val = str(val)
            cell = clean_val.ljust(w)
            if "Up" in clean_val or "healthy" in clean_val or "running" in clean_val or "ok" in clean_val:
                cell = c(cell, "green")
            elif "Exited" in clean_val or "unhealthy" in clean_val or "falhou" in clean_val or "degraded" in clean_val:
                cell = c(cell, "red")
            elif "restarting" in clean_val or "pending" in clean_val:
                cell = c(cell, "yellow")
            colored_row.append(cell)
        print(" " + " │ ".join(colored_row))


def require_project() -> None:
    if not PROJECT_DIR.exists():
        fail(f"Diretorio do projeto nao encontrado: {PROJECT_DIR}")
    if not COMPOSE_FILE.exists():
        fail(f"compose.yml nao encontrado em: {COMPOSE_FILE}")


def run(
    args: list[str],
    *,
    check: bool = True,
    capture: bool = False,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd or PROJECT_DIR),
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )


def compose_args(*parts: str) -> list[str]:
    return ["docker", "compose", "-f", str(COMPOSE_FILE), *parts]


def compose(*parts: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
    require_project()
    return run(compose_args(*parts), check=check, capture=capture)


def read_env() -> dict[str, str]:
    if not ENV_FILE.exists():
        return {}
    values: dict[str, str] = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def write_env_value(key: str, value: str) -> None:
    if not re.fullmatch(r"[A-Z0-9_]+", key):
        fail("Nome de variavel invalido. Use apenas A-Z, 0-9 e underscore.")
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    new_line = f"{key}={value}"
    changed = False
    for index, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[index] = new_line
            changed = True
            break
    if not changed:
        lines.append(new_line)
    ENV_FILE.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    ok(f"{key} atualizado em {ENV_FILE}")


def redact(key: str, value: str) -> str:
    if any(part in key.upper() for part in SECRET_NAMES):
        if not value:
            return ""
        return value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
    return value


def health_json(path: str) -> dict | None:
    url = DEFAULT_HEALTH_URL + path
    try:
        with urlopen(url, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError):
        return None


def print_json(data: object) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def status(_: argparse.Namespace | None = None) -> None:
    header("ESTADO ATUAL DO SISTEMA")
    
    # 1. Fetch containers nicely
    try:
        res = compose("ps", "--format", "json", capture=True, check=False)
        # Docker output can be list of lines, each being a JSON
        containers = []
        for line in res.stdout.strip().splitlines():
            if not line.strip(): continue
            try:
                j = json.loads(line)
                if isinstance(j, list):
                    containers.extend(j)
                else:
                    containers.append(j)
            except json.JSONDecodeError:
                continue
        
        if containers:
            rows = []
            for ct in containers:
                name = ct.get("Name", ct.get("Names", "??"))
                svc = ct.get("Service", "??")
                state = ct.get("State", "??")
                status_str = ct.get("Status", "??")
                rows.append([svc, name, state, status_str])
            print_table(["SERVIÇO", "NOME DO CONTAINER", "ESTADO", "DETALHE"], rows)
        else:
            warn("Nenhum container em execução.")
    except Exception:
        info("Containers (Modo Legado)")
        compose("ps", check=False)

    # 2. Health endpoints in table
    header("RESUMO DE INTEGRAÇÕES")
    h_rows = []
    for name, path in [("API Backend", "/health"), ("Motor IA", "/health/runtime"), ("Integração GLPI", "/health/glpi")]:
        data = health_json(path)
        if data is None:
            h_rows.append([name, path, "offline", "Conexão recusada ou indisponível"])
        else:
            st = str(data.get("status", "unknown"))
            detail = "OK" if st == "ok" else str(data.get("error", str(data.get("message", "Erro ou Falha"))))
            h_rows.append([name, path, st, detail[:50]])
    print_table(["MÓDULO", "ENDPOINT", "STATUS", "INFO"], h_rows)

    # 3. Important config inline
    header("CONFIGURAÇÃO ATIVA")
    env = read_env()
    k_list = ("APP_ENV", "GLPI_INTEGRATION_MODE", "LOCAL_LIGHT_AI_MODE", "STATE_BACKEND", "ALLOWED_NUMBERS")
    for key in k_list:
        val = env.get(key, c("NÃO DEFINIDO", "dim"))
        clean_val = redact(key, str(val))
        print(f"  {c('>', 'cyan')} " + c(key.ljust(25), "white+bold") + " : " + c(clean_val, "yellow"))
    print()


def up(args: argparse.Namespace) -> None:
    parts = ["up", "-d"]
    if args.build:
        parts.append("--build")
    if args.services:
        parts.extend(args.services)
    compose(*parts)
    status(None)


def down(args: argparse.Namespace) -> None:
    parts = ["down"]
    if args.volumes:
        if args.yes or confirm("Isto remove volumes Docker persistentes. Continuar?"):
            parts.append("--volumes")
        else:
            warn("Cancelado.")
            return
    compose(*parts)


def restart(args: argparse.Namespace) -> None:
    parts = ["restart"]
    parts.extend(args.services or [])
    compose(*parts)
    status(None)


def logs(args: argparse.Namespace) -> None:
    service = getattr(args, "service", "all") or "all"
    if service and service not in SERVICES and service != "all":
        fail(f"Servico invalido. Use: {', '.join(SERVICES)} ou all")
    
    base_parts = compose_args("logs", f"--tail={getattr(args, 'tail', 150)}")
    if getattr(args, "follow", False):
        base_parts.append("-f")
    
    since_str = getattr(args, "since", None)
    if since_str:
        base_parts.append(f"--since={since_str}")
        
    if service and service != "all":
        base_parts.append(service)
    
    # Use full system shell to allow correct terminal passthrough of color codes & pipes
    cmd_str = shlex.join(base_parts)
    
    grep_str = getattr(args, "grep", None)
    if grep_str:
        # Protect the grep string and enforce line-buffering for live tracking
        safe_grep = shlex.quote(grep_str)
        cmd_str += f" | grep --line-buffered -i --color=always {safe_grep}"

    # Pass direct to user shell context to handle raw streams and CTRL+C correctly
    os.system(cmd_str)


def env_cmd(args: argparse.Namespace) -> None:
    env = read_env()
    if args.env_action == "show":
        for key in sorted(env):
            print(f"{key}={redact(key, env[key])}")
    elif args.env_action == "get":
        value = env.get(args.key, "")
        print(redact(args.key, value))
    elif args.env_action == "set":
        write_env_value(args.key, args.value)
        warn("Recrie os containers para aplicar: botctl restart web whatsapp worker-ai worker-glpi")


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("55") and len(digits) >= 12:
        digits = digits[2:]
    return digits


def allowlist(args: argparse.Namespace) -> None:
    env = read_env()
    current = [n for n in env.get("ALLOWED_NUMBERS", "").split(",") if n.strip()]
    normalized = normalize_phone(args.number) if getattr(args, "number", None) else ""

    if args.allow_action == "show":
        print("ALLOW_ALL_NUMBERS=" + env.get("ALLOW_ALL_NUMBERS", "false"))
        print("ALLOWED_NUMBERS=" + ",".join(current))
        return
    if args.allow_action == "add":
        if not normalized:
            fail("Informe um telefone valido.")
        if normalized not in current:
            current.append(normalized)
        write_env_value("ALLOWED_NUMBERS", ",".join(current))
    elif args.allow_action == "remove":
        current = [n for n in current if n != normalized]
        write_env_value("ALLOWED_NUMBERS", ",".join(current))
    elif args.allow_action == "set":
        values = [normalize_phone(value) for value in args.numbers.split(",")]
        values = [value for value in values if value]
        if not values:
            fail("Lista vazia. Informe ao menos um numero.")
        write_env_value("ALLOWED_NUMBERS", ",".join(dict.fromkeys(values)))
    elif args.allow_action == "all-on":
        write_env_value("ALLOW_ALL_NUMBERS", "true")
    elif args.allow_action == "all-off":
        write_env_value("ALLOW_ALL_NUMBERS", "false")
    warn("Reinicie o conector para aplicar: botctl restart whatsapp")


def redis_cli(*parts: str, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(
        ["docker", "exec", "bot-chamados-redis", "redis-cli", *parts],
        check=check,
        capture=capture,
    )


def redis_cmd(args: argparse.Namespace) -> None:
    phone = normalize_phone(getattr(args, "phone", "") or "")
    key = f"channel_link:whatsapp:{phone}" if phone else ""

    if args.redis_action == "keys":
        result = redis_cli("--scan", "--pattern", "channel_link:*", capture=True, check=False)
        print(result.stdout or "")
    elif args.redis_action == "show-link":
        if not key:
            fail("Informe o telefone.")
        result = redis_cli("GET", key, capture=True, check=False)
        raw = (result.stdout or "").strip()
        if not raw:
            warn("Vinculo nao encontrado.")
            return
        try:
            print_json(json.loads(raw))
        except json.JSONDecodeError:
            print(raw)
    elif args.redis_action == "delete-link":
        if not key:
            fail("Informe o telefone.")
        result = redis_cli("DEL", key, capture=True, check=False)
        print((result.stdout or "").strip())
        ok(f"Chave removida se existia: {key}")
    elif args.redis_action == "flush":
        if args.yes or confirm("FLUSHALL apaga estado, vinculos e filas Redis. Continuar?"):
            redis_cli("FLUSHALL")
        else:
            warn("Cancelado.")


def doctor(_: argparse.Namespace | None = None) -> None:
    header("DIAGNÓSTICO COMPLETO DO SISTEMA")
    
    checks = [
        ("Raiz do Projeto", PROJECT_DIR, PROJECT_DIR.exists()),
        ("Arquivo Compose", COMPOSE_FILE, COMPOSE_FILE.exists()),
        ("Arquivo Env Vars", ENV_FILE, ENV_FILE.exists()),
    ]
    
    d_rows = []
    for label, path, exists in checks:
        status_txt = "ok" if exists else "falhou"
        detail = str(path) if exists else "NÃO ENCONTRADO"
        d_rows.append([label, status_txt, detail])
        
    print_table(["RECURSO", "ESTADO", "CAMINHO / NOTA"], d_rows)
    print()
    
    info("Versão do Daemon do Docker:")
    try:
        run(["docker", "info", "--format", "  - Engine: {{.ServerVersion}}\n  - Driver: {{.Driver}}\n  - CPUs: {{.NCPU}}\n  - Memória: {{.MemTotal}} bytes"], check=False)
    except Exception:
        pass
        
    print()
    status(None)


def qr(args: argparse.Namespace) -> None:
    args.service = "whatsapp"
    args.follow = True
    args.tail = 180
    logs(args)


def confirm(question: str) -> bool:
    answer = input(f"{question} Digite SIM para confirmar: ").strip()
    return answer == "SIM"


def menu_logs() -> None:
    print(c("ASSISTENTE AVANÇADO DE LOGS", "cyan+bold"))
    
    # 1. Service Selection
    print("\nEscolha o Serviço:")
    print("  0. Todos os serviços (Geral)")
    for idx, svc in enumerate(SERVICES, 1):
        print(f"  {idx}. {svc}")
    
    try:
        svc_choice = input(c("\nEscolha [0]: ", "green")).strip() or "0"
        if svc_choice == "0":
            service = "all"
        else:
            service = SERVICES[int(svc_choice) - 1]
    except (ValueError, IndexError):
        warn("Opção inválida. Usando 'all'.")
        service = "all"

    # 2. Tail Definition
    print("\nQuantidade de linhas retroativas (Tail):")
    print("  1. 100 linhas")
    print("  2. 500 linhas")
    print("  3. 2000 linhas (Geralmente cobre o dia)")
    print("  4. Todo o histórico disponível (Pode ser lento)")
    
    tail_choice = input(c("\nEscolha [1]: ", "green")).strip() or "1"
    tail_map = {"1": 100, "2": 500, "3": 2000, "4": "all"}
    tail_lines = tail_map.get(tail_choice, 100)

    # 3. Since/Datetime Filter
    print("\nFiltrar por Período de Tempo (Since):")
    print("  0. Não filtrar por tempo")
    print("  1. Últimos 10 minutos (10m)")
    print("  2. Última 1 hora (1h)")
    print("  3. Últimas 24 horas (24h)")
    print("  4. Personalizado (ex: 2026-05-11T15:00:00 ou 2h)")
    
    since_choice = input(c("\nEscolha [0]: ", "green")).strip() or "0"
    since_val = None
    if since_choice == "1":
        since_val = "10m"
    elif since_choice == "2":
        since_val = "1h"
    elif since_choice == "3":
        since_val = "24h"
    elif since_choice == "4":
        since_val = input(c("\nDigite a janela tempo (ex: 30m ou 2026-01-01): ", "green")).strip()

    # 4. Follow Mode
    follow_raw = input(c("\nDeseja acompanhar em tempo real? (Live/Follow) [S/n]: ", "green")).strip().lower()
    follow = follow_raw != "n"

    # 5. Grep Filter
    print(c("\nFiltro de Conteúdo (Opcional):", "dim"))
    print("Exemplo: 'Error', 'POST', 'User ID', 'GLPI'")
    grep_val = input(c("Palavra-chave para filtrar (Vazio para nenhum): ", "green")).strip()

    # Run
    header(f"EXIBINDO LOGS: {service.upper()}")
    det = []
    if tail_lines: det.append(f"Tail={tail_lines}")
    if since_val: det.append(f"Since={since_val}")
    if grep_val: det.append(f"Grep='{grep_val}'")
    if det: info("Configurações: " + " | ".join(det))
    
    print(c("Pressione CTRL+C para encerrar e voltar ao menu.\n", "dim"))
    
    ns = argparse.Namespace(
        service=service, 
        tail=tail_lines, 
        since=since_val,
        follow=follow, 
        grep=grep_val if grep_val else None
    )
    logs(ns)


def interactive(_: argparse.Namespace | None = None) -> None:
    # Logical grouping definition
    layout = {
        "TELEMETRIA & STATUS": {
            "1": ("Visualizar Status Geral", lambda: status(None)),
            "11": ("Diagnóstico de Infraestrutura", lambda: doctor(None)),
            "6": ("Assistente Avançado de Logs", menu_logs),
        },
        "CONTROLE DA STACK": {
            "2": ("Ligar Todos os Serviços", lambda: up(argparse.Namespace(build=False, services=[]))),
            "3": ("Reconstruir (Build) + Ligar", lambda: up(argparse.Namespace(build=True, services=[]))),
            "4": ("Reiniciar Serviço WhatsApp", lambda: restart(argparse.Namespace(services=["whatsapp"]))),
            "10": ("Desligar e Parar stack", lambda: down(argparse.Namespace(volumes=False, yes=False))),
        },
        "CANAL WHATSAPP": {
            "5": ("Visualizar QR Code Ativo", lambda: qr(argparse.Namespace())),
            "7": ("Consultar Firewall/Allowlist", lambda: allowlist(argparse.Namespace(allow_action="show"))),
            "8": ("Liberar Novo Telefone (Allowlist)", menu_add_allowlist),
            "9": ("Excluir Vínculo de Autenticação", menu_delete_link),
        },
        "SISTEMA": {
            "12": ("Manual Técnico de Parâmetros", lambda: config_docs(None)),
            "cls": ("Limpar Tela do Console", clear_screen),
        }
    }

    # Flatten lookup for efficiency
    actions = {}
    for g in layout.values():
        actions.update(g)

    while True:
        clear_screen()
        banner()
        print(c("═"*60, "dim"))
        
        for group_title, items in layout.items():
            print(c(f"\n {group_title} ", "white+bg_blue"))
            for k, (label, _) in items.items():
                # Align keys cleanly
                idx = k.rjust(3)
                print(f"  {c(idx, 'cyan+bold')} {c('->', 'dim')} {label}")
        
        print(c("\n  0 -> Sair do Terminal\n", "red+dim"))
        
        try:
            choice = input(c("Digite o comando ❯ ", "green+bold")).strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSaindo...")
            return
            
        if choice == "0" or choice.lower() in ('q', 'exit', 'quit'):
            clear_screen()
            print(c("Operacao encerrada.", "dim"))
            return

        action = actions.get(choice)
        if not action:
            warn("Opcao invalida.")
            input("\nPressione Enter para continuar...")
            continue

        clear_screen()
        header(f"Executando: {choice}")
        try:
            action[1]()
        except KeyboardInterrupt:
            print()
            warn("Interrompido pelo usuario.")
        except subprocess.CalledProcessError as exc:
            fail(f"Falha: {shlex.join(exc.cmd)}", code=1)
        
        print("\n" + c("─"*60, "dim"))
        input(c("\nPressione Enter para voltar ao menu...", "dim"))


def menu_add_allowlist() -> None:
    number = input("Telefone com DDD: ").strip()
    allowlist(argparse.Namespace(allow_action="add", number=number))


def menu_delete_link() -> None:
    number = input("Telefone com DDD: ").strip()
    redis_cmd(argparse.Namespace(redis_action="delete-link", phone=number))


def config_docs(_: argparse.Namespace | None = None) -> None:
    print(c("\n" + "="*60, "bold"))
    print(c(" MANUAL DE PARAMETRIZAÇÃO - ARQUIVO .env.docker ", "bold"))
    print(c("="*60, "bold"))
    print("\nConsulte este guia para entender o que cada variável altera no comportamento do bot.\n")

    env_atual = read_env()

    for group, variables in CONFIG_MANUAL.items():
        print(c(f"\n> {group}", "cyan"))
        print(c("-" * len(group) * 2, "cyan"))
        
        for var, description in variables.items():
            status_icon = c("[+]", "green") if var in env_atual else c("[ ]", "red")
            print(f" {status_icon} " + c(f"{var}", "bold"))
            print(f"    Descricao: {description}")
            current_val = redact(var, env_atual.get(var, "NAO DEFINIDO"))
            print(f"    Valor Atual: " + c(current_val, "yellow" if var in env_atual else "red"))
            print()
    
    print(c("\nPara alterar um valor use: botctl env set [NOME] [VALOR]", "cyan"))


def show_help(_: argparse.Namespace | None = None) -> None:
    print(c("\n--- GUIA RAPIDO DE COMANDOS - botctl ---\n", "bold"))
    print("O `botctl` e o painel de controle do Bot de Chamados no Proxmox.\n")
    
    print(c("Diagnostico e Status:", "cyan"))
    print("  botctl status                      Mostra containers, health endpoints e configuracao atual.")
    print("  botctl doctor                      Executa um diagnostico rapido da infraestrutura.")
    print("  botctl menu                        Abre o menu interativo amigavel.")
    print()
    print(c("Controle da Stack Docker:", "cyan"))
    print("  botctl up [--build] [servicos]     Sobe os containers (ex: botctl up --build web).")
    print("  botctl down [--volumes]            Para todos os containers e limpa volumes se solicitado.")
    print("  botctl restart [servicos]          Reinicia servicos (ex: botctl restart whatsapp).")
    print()
    print(c("Logs e Pareamento:", "cyan"))
    print("  botctl logs [servico] [-f]         Mostra logs em tempo real (ex: botctl logs web -f).")
    print("  botctl qr                          Segue logs do WhatsApp para exibir o QR Code ativo.")
    print()
    print(c("Configuracoes e Variaveis (.env):", "cyan"))
    print("  botctl env show                    Lista todas as variaveis de ambiente ativas.")
    print("  botctl env get [CHAVE]             Exibe o valor de uma chave especifica.")
    print("  botctl env set [CHAVE] [VALOR]     Define o valor de uma chave no .env.docker.")
    print("  botctl config-docs                 Exibe o manual detalhado com descrições de cada parâmetro.")
    print()
    print(c("Controle de Acesso (Allowlist):", "cyan"))
    print("  botctl allowlist show              Mostra numeros permitidos e status do bloqueio.")
    print("  botctl allowlist add [FONE]        Adiciona um numero a lista de permitidos.")
    print("  botctl allowlist remove [FONE]     Remove um numero da lista de permitidos.")
    print("  botctl allowlist all-on / all-off  Ativa ou desativa o acesso publico irrestrito.")
    print()
    print(c("Persistencia de Vinculos (Redis):", "cyan"))
    print("  botctl redis keys                  Lista todas as chaves de vinculos de sessao.")
    print("  botctl redis show-link [FONE]      Mostra dados de login e CPF vinculados ao telefone.")
    print("  botctl redis delete-link [FONE]    Remove o vinculo e forca nova autenticacao via CPF.")
    print("  botctl redis flush                 Apaga todos os vinculos, estados e filas do Redis.\n")
    print("Para ajuda do proprio interpretador, digite: " + c("botctl --help", "yellow") + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="botctl",
        description="Painel terminal do Bot-Chamados-GLPI para Proxmox/LXC.",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="Mostra containers, health e configuracao.").set_defaults(func=status)
    sub.add_parser("doctor", help="Diagnostico completo.").set_defaults(func=doctor)
    sub.add_parser("menu", help="Abre menu interativo.").set_defaults(func=interactive)
    sub.add_parser("help", help="Mostra o guia rápido de comandos.").set_defaults(func=show_help)
    sub.add_parser("config-docs", help="Manual detalhado do .env.").set_defaults(func=config_docs)

    p_up = sub.add_parser("up", help="Sobe a stack.")
    p_up.add_argument("--build", action="store_true", help="Rebuild das imagens.")
    p_up.add_argument("services", nargs="*", help="Servicos opcionais.")
    p_up.set_defaults(func=up)

    p_down = sub.add_parser("down", help="Desce a stack.")
    p_down.add_argument("--volumes", action="store_true", help="Remove volumes.")
    p_down.add_argument("-y", "--yes", action="store_true", help="Confirma operacoes destrutivas.")
    p_down.set_defaults(func=down)

    p_restart = sub.add_parser("restart", help="Reinicia servicos.")
    p_restart.add_argument("services", nargs="*", help="Servicos. Vazio reinicia todos.")
    p_restart.set_defaults(func=restart)

    p_logs = sub.add_parser("logs", help="Mostra logs.")
    p_logs.add_argument("service", nargs="?", default="all", help="Servico ou all.")
    p_logs.add_argument("-f", "--follow", action="store_true", help="Segue logs.")
    p_logs.add_argument("--tail", type=str, default="150", help="Quantidade de linhas.")
    p_logs.add_argument("--since", type=str, default=None, help="Filtrar por tempo (ex: 1h).")
    p_logs.add_argument("-g", "--grep", type=str, default=None, help="Filtro de conteudo.")
    p_logs.set_defaults(func=logs)

    sub.add_parser("qr", help="Segue logs do WhatsApp para QR/conexao.").set_defaults(func=qr)

    p_env = sub.add_parser("env", help="Consulta/altera .env.docker.")
    env_sub = p_env.add_subparsers(dest="env_action", required=True)
    env_sub.add_parser("show")
    p_env_get = env_sub.add_parser("get")
    p_env_get.add_argument("key")
    p_env_set = env_sub.add_parser("set")
    p_env_set.add_argument("key")
    p_env_set.add_argument("value")
    p_env.set_defaults(func=env_cmd)

    p_allow = sub.add_parser("allowlist", help="Gerencia ALLOWED_NUMBERS.")
    allow_sub = p_allow.add_subparsers(dest="allow_action", required=True)
    allow_sub.add_parser("show")
    p_allow_add = allow_sub.add_parser("add")
    p_allow_add.add_argument("number")
    p_allow_remove = allow_sub.add_parser("remove")
    p_allow_remove.add_argument("number")
    p_allow_set = allow_sub.add_parser("set")
    p_allow_set.add_argument("numbers", help="Lista separada por virgula.")
    allow_sub.add_parser("all-on")
    allow_sub.add_parser("all-off")
    p_allow.set_defaults(func=allowlist)

    p_redis = sub.add_parser("redis", help="Estado de autenticacao no Redis.")
    redis_sub = p_redis.add_subparsers(dest="redis_action", required=True)
    redis_sub.add_parser("keys")
    p_show_link = redis_sub.add_parser("show-link")
    p_show_link.add_argument("phone")
    p_delete_link = redis_sub.add_parser("delete-link")
    p_delete_link.add_argument("phone")
    p_flush = redis_sub.add_parser("flush")
    p_flush.add_argument("-y", "--yes", action="store_true")
    p_redis.set_defaults(func=redis_cmd)

    return parser


def main(argv: Iterable[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if not getattr(args, "command", None):
        interactive(None)
        return
    args.func(args)


if __name__ == "__main__":
    main()
