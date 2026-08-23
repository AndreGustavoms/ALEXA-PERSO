@echo off
setlocal
title Instalador do Doktor Assistant
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install-assistant.ps1"
if errorlevel 1 (
  echo.
  echo A instalacao nao foi concluida. Confira a mensagem acima.
  pause
  exit /b 1
)

echo.
echo Doktor Assistant instalado e iniciado em segundo plano.
timeout /t 3 >nul
