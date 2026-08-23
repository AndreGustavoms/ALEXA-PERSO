@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Execute INSTALAR_ASSISTENTE.cmd primeiro.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m assistant_runtime.configure_openai
if errorlevel 1 pause & exit /b 1
cscript //nologo "INICIAR_ASSISTENTE.vbs" restart
pause
