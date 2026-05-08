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

try:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (AttributeError, ValueError):
    pass


def c(text: str, color: str) -> str:
    colors = {
        "red": "\033[31m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "cyan": "\033[36m",
        "bold": "\033[1m",
        "reset": "\033[0m",
    }
    if not sys.stdout.isatty():
        return text
    return f"{colors.get(color, '')}{text}{colors['reset']}"


def info(text: str) -> None:
    print(c(f"==> {text}", "cyan"), flush=True)


def ok(text: str) -> None:
    print(c(f"[OK] {text}", "green"), flush=True)


def warn(text: str) -> None:
    print(c(f"[!] {text}", "yellow"), flush=True)


def fail(text: str, code: int = 1) -> None:
    print(c(f"[ERRO] {text}", "red"), file=sys.stderr)
    raise SystemExit(code)


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
    info("Containers")
    compose("ps", check=False)
    print()
    info("Health")
    for path in ("/health", "/health/runtime", "/health/glpi"):
        data = health_json(path)
        if data is None:
            warn(f"{path}: indisponivel")
        else:
            print(f"{path}:")
            print_json(data)
    print()
    info("Configuracao resumida")
    env = read_env()
    for key in (
        "APP_ENV",
        "GLPI_INTEGRATION_MODE",
        "GLPI_BASE_URL",
        "STATE_BACKEND",
        "USE_CELERY_WORKERS",
        "ALLOWED_NUMBERS",
        "ALLOW_ALL_NUMBERS",
        "LOG_IGNORED_MESSAGES",
    ):
        print(f"{key}={redact(key, env.get(key, ''))}")


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
    service = args.service
    if service and service not in SERVICES and service != "all":
        fail(f"Servico invalido. Use: {', '.join(SERVICES)} ou all")
    parts = ["logs", f"--tail={args.tail}"]
    if args.follow:
        parts.append("-f")
    if service and service != "all":
        parts.append(service)
    compose(*parts, check=False)


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
    info("Diagnostico rapido")
    checks = [
        ("Projeto", PROJECT_DIR.exists()),
        ("compose.yml", COMPOSE_FILE.exists()),
        (".env.docker", ENV_FILE.exists()),
    ]
    for name, passed in checks:
        print(f"{name}: {'ok' if passed else 'falhou'}")
    print()
    run(["docker", "info", "--format", "Docker: {{.ServerVersion}} / driver {{.Driver}}"], check=False)
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


def interactive(_: argparse.Namespace | None = None) -> None:
    actions = {
        "1": ("Status geral", lambda: status(None)),
        "2": ("Subir stack", lambda: up(argparse.Namespace(build=False, services=[]))),
        "3": ("Rebuild + subir stack", lambda: up(argparse.Namespace(build=True, services=[]))),
        "4": ("Reiniciar WhatsApp", lambda: restart(argparse.Namespace(services=["whatsapp"]))),
        "5": ("Logs WhatsApp ao vivo / QR", lambda: qr(argparse.Namespace())),
        "6": ("Logs Web", lambda: logs(argparse.Namespace(service="web", follow=False, tail=160))),
        "7": ("Ver allowlist", lambda: allowlist(argparse.Namespace(allow_action="show"))),
        "8": ("Adicionar numero na allowlist", menu_add_allowlist),
        "9": ("Remover vinculo de autenticacao", menu_delete_link),
        "10": ("Descer stack", lambda: down(argparse.Namespace(volumes=False, yes=False))),
        "11": ("Diagnostico completo", lambda: doctor(None)),
        "0": ("Sair", None),
    }
    while True:
        print()
        print(c("Bot-Chamados-GLPI - painel terminal", "bold"))
        for key, (label, _) in actions.items():
            print(f"{key}. {label}")
        choice = input("Escolha: ").strip()
        if choice == "0":
            return
        action = actions.get(choice)
        if not action:
            warn("Opcao invalida.")
            continue
        print()
        try:
            action[1]()
        except KeyboardInterrupt:
            print()
            warn("Interrompido.")
        except subprocess.CalledProcessError as exc:
            fail(f"Comando falhou: {shlex.join(exc.cmd)}", code=1)


def menu_add_allowlist() -> None:
    number = input("Telefone com DDD: ").strip()
    allowlist(argparse.Namespace(allow_action="add", number=number))


def menu_delete_link() -> None:
    number = input("Telefone com DDD: ").strip()
    redis_cmd(argparse.Namespace(redis_action="delete-link", phone=number))


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
    p_logs.add_argument("--tail", type=int, default=120, help="Quantidade de linhas.")
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
