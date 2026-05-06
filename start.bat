@echo off
setlocal
title Assistente de Chamados TI - Orquestrador
color 0B

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_all.ps1" %*

echo.
pause
