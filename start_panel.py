import os
import subprocess
import sys
import socket
import time

# Cores Corporativas (Padrão New Holland: Azul e Amarelo)
BLUE = '\033[94m'
YELLOW = '\033[93m'
WHITE = '\033[97m'
GREEN = '\033[92m'
RED = '\033[91m'
BOLD = '\033[1m'
RESET = '\033[0m'

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    print(f"{BLUE}{BOLD}")
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║                                                                  ║")
    print(f"║{YELLOW}      TERRA PREMIUM - NEW HOLLAND AGRICULTURE                     {BLUE}║")
    print("║      ASSISTENTE DE CHAMADOS TI ON-PREMISE (GLPI)                 ║")
    print("║                                                                  ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print("║      ADMINISTRATION & ORCHESTRATION PANEL - v1.0.0               ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print(f"{RESET}")

def check_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def configure_network():
    print(f"{BOLD}{BLUE}[ SYSTEM CONFIGURATION ]{RESET}\n")
    if "--auto" in sys.argv:
        return "0.0.0.0", "8000", ""
        
    port_str = input(f" {YELLOW}▸{RESET} Porta da API FastAPI {WHITE}[Padrão: 8000]:{RESET} ")
    port = port_str if port_str.strip() else "8000"
    
    host_str = input(f" {YELLOW}▸{RESET} Host de Bind {WHITE}[Padrão: 0.0.0.0]:{RESET} ")
    host = host_str if host_str.strip() else "0.0.0.0"
    
    print(f"\n{BOLD}{YELLOW}[ SANDBOX MODE / ISOLAMENTO ]{RESET}")
    print(f" {WHITE}Insira o número de telefone (com DDD) que será permitido usar o bot.{RESET}")
    print(f" {WHITE}Se deixado em branco, TODOS os contatos poderão usar.{RESET}")
    allowed_numbers = input(f" {YELLOW}▸{RESET} Número Permitido (ex: 66999990980): ")
    
    return host, port, allowed_numbers.strip()

def check_dependencies():
    print(f"\n{BOLD}{BLUE}[ DEPENDENCY HEALTH-CHECK ]{RESET}\n")
    
    # Check Redis
    print(f" {YELLOW}▸{RESET} Verificando Redis Database...", end=" ")
    if check_port(6379):
        print(f"[{GREEN}ONLINE{RESET}]")
    else:
        print(f"[{RED}OFFLINE{RESET}]")
        print(f"   {RED}↳ Alerta: Redis não detectado na porta 6379.{RESET}")
        if "--auto" not in sys.argv:
            input(f"   Pressione Enter para ignorar e continuar...")

    # Check Ollama
    print(f" {YELLOW}▸{RESET} Verificando Engine de IA (Ollama)...", end=" ")
    if check_port(11434):
        print(f"[{GREEN}ONLINE{RESET}]")
    else:
        print(f"[{RED}OFFLINE{RESET}]")
        print(f"   {RED}↳ Alerta: Ollama não detectado na porta 11434.{RESET}")
        if "--auto" not in sys.argv:
            input(f"   Pressione Enter para ignorar e continuar...")

def start_services(host, port, allowed_numbers):
    print(f"\n{BOLD}{GREEN}>>> INICIANDO SERVIÇOS DO ECOSSISTEMA <<< {RESET}\n")
    
    # Inicia a FastAPI
    fastapi_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", host, "--port", port],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    print(f" [{GREEN}✓{RESET}] Core API (Motor Conversacional)   -> {BLUE}http://{host}:{port}{RESET}")

    # Configura variáveis de ambiente para o Go (Sandbox Mode)
    env = os.environ.copy()
    if allowed_numbers:
        env["ALLOWED_NUMBERS"] = allowed_numbers
        print(f" [{GREEN}✓{RESET}] Sandbox Mode Ativado            -> {YELLOW}Apenas o número {allowed_numbers} tem acesso!{RESET}")
    else:
        print(f" [{RED}!{RESET}] Sandbox Mode Desativado         -> {RED}Modo Público (Todos podem acessar!){RESET}")

    # Inicia o Go
    go_path = r"C:\Program Files\Go\bin\go.exe" if os.name == 'nt' else "go"
    print(f" [{GREEN}✓{RESET}] Serviço WhatsApp (WhatsMeow)      -> {BLUE}Iniciando...{RESET}\n")
    print(f" {YELLOW}» Aguarde o QR Code de Autenticação corporativa abaixo...{RESET}\n")
    
    try:
        go_process = subprocess.Popen(
            [go_path, "run", "main.go"],
            cwd=os.path.join(os.getcwd(), "whatsapp_connector"),
            env=env,
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        go_process.wait()
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Desligando serviços corporativos de forma segura...{RESET}")
        go_process.terminate()
        fastapi_process.terminate()
        print(f"{GREEN}Sistema encerrado com sucesso.{RESET}")

if __name__ == "__main__":
    clear_screen()
    print_banner()
    host, port, allowed_numbers = configure_network()
    check_dependencies()
    start_services(host, port, allowed_numbers)
