$ErrorActionPreference = 'Stop'

$projectDirectory = Split-Path -Parent $PSScriptRoot
$venvDirectory = Join-Path $projectDirectory '.venv'
$pythonPath = Join-Path $venvDirectory 'Scripts\python.exe'
$launcherPath = Join-Path $projectDirectory 'INICIAR_ASSISTENTE.vbs'
$iconPath = Join-Path $projectDirectory 'assets\doktor-assistant.ico'

Set-Location -LiteralPath $projectDirectory

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  throw 'Python 3 não foi encontrado neste computador.'
}

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  throw 'Node.js não foi encontrado neste computador.'
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  throw 'O npm não foi encontrado neste computador.'
}

Write-Host 'Preparando o ambiente local...'
if (-not (Test-Path -LiteralPath $pythonPath)) {
  & python -m venv $venvDirectory
  if ($LASTEXITCODE -ne 0) {
    throw 'Não foi possível criar o ambiente Python.'
  }
}

Write-Host 'Encerrando a versao anterior, se estiver ativa...'
& $pythonPath (Join-Path $projectDirectory 'assistant_runtime\main.py') --stop
if ($LASTEXITCODE -eq 0) {
  for ($attempt = 0; $attempt -lt 40; $attempt++) {
    $activeConnection = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue
    if (-not $activeConnection) {
      break
    }
    Start-Sleep -Milliseconds 250
  }
}

Write-Host 'Instalando os componentes de voz...'
& $pythonPath -m pip install --disable-pip-version-check -r (Join-Path $projectDirectory 'assistant_runtime\requirements.txt')
if ($LASTEXITCODE -ne 0) {
  throw 'Não foi possível instalar os componentes de voz.'
}

& $pythonPath (Join-Path $projectDirectory 'assistant_runtime\setup_model.py')
if ($LASTEXITCODE -ne 0) {
  throw 'Não foi possível instalar o modelo de reconhecimento.'
}

& $pythonPath (Join-Path $projectDirectory 'assistant_runtime\create_icon.py')
if ($LASTEXITCODE -ne 0) {
  throw 'Não foi possível criar o ícone do aplicativo.'
}

Write-Host 'Preparando a interface...'
& npm install
if ($LASTEXITCODE -ne 0) {
  throw 'Não foi possível instalar a interface.'
}

& npm run build
if ($LASTEXITCODE -ne 0) {
  throw 'Não foi possível gerar a interface local.'
}

$shell = New-Object -ComObject WScript.Shell
$desktopDirectory = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktopDirectory 'Doktor Assistant.lnk'
$legacyShortcutPath = Join-Path $desktopDirectory 'Assistente de voz.lnk'
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $env:WINDIR 'System32\wscript.exe'
$shortcut.Arguments = "//nologo `"$launcherPath`" open"
$shortcut.WorkingDirectory = $projectDirectory
$shortcut.IconLocation = "$iconPath,0"
$shortcut.Description = 'Abrir a Doktor Assistant em segundo plano'
$shortcut.Save()
Remove-Item -LiteralPath $legacyShortcutPath -Force -ErrorAction SilentlyContinue

& $pythonPath (Join-Path $projectDirectory 'assistant_runtime\main.py') --install-autostart
if ($LASTEXITCODE -ne 0) {
  throw 'Não foi possível configurar a inicialização com o Windows.'
}

Write-Host 'Iniciando a Doktor Assistant...'
Start-Process -FilePath (Join-Path $env:WINDIR 'System32\wscript.exe') `
  -ArgumentList @('//nologo', "`"$launcherPath`"", 'open') `
  -WorkingDirectory $projectDirectory `
  -WindowStyle Hidden
