@echo off
title Assistente de Chamados TI - Orquestrador
color 0B

echo ===================================================
echo   Assistente de Chamados TI - New Holland
echo ===================================================
echo.
echo [1/2] Verificando e subindo servidores no Docker (WSL/Ubuntu)...
wsl -d Ubuntu-24.04 -u root sh -c "cd /mnt/c/projects/Bot-Chamados-GLPI && docker compose up -d"

echo.
echo [2/2] Iniciando Conector do WhatsApp...
echo.
echo Aviso: O Sandbox esta ATIVADO para o numero 66999990980.
echo Qualquer outro numero sera ignorado automaticamente.
echo.

:: Configurando Sandbox (Apenas este numero sera respondido)
set ALLOWED_NUMBERS=66999990980

:: Navega e roda o Golang
cd whatsapp_connector
go run main.go

pause
