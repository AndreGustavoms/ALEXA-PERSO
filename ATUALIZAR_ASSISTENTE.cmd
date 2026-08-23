@echo off
setlocal
title Atualizar Doktor Assistant
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\update-assistant.ps1" -Force -Restart
if errorlevel 1 (
  echo.
  echo A atualizacao nao foi concluida. O aplicativo anterior foi preservado.
  pause
  exit /b 1
)

echo.
echo Doktor Assistant atualizado.
timeout /t 3 >nul
