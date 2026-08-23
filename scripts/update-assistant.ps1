param(
  [switch]$Force,
  [switch]$Restart,
  [switch]$Silent
)

$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path -Parent $PSScriptRoot
$repository = 'AndreGustavoms/ALEXA-PERSO'
$branch = 'main'
$stateDirectory = Join-Path $projectDirectory 'runtime\config'
$statePath = Join-Path $stateDirectory 'update-state.json'
$temporaryRoot = Join-Path ([IO.Path]::GetTempPath()) ('doktor-assistant-update-' + [guid]::NewGuid().ToString('N'))

function Write-UpdateStatus([string]$message) {
  if (-not $Silent) {
    Write-Host $message
  }
}

function Save-UpdateState([string]$sha) {
  New-Item -ItemType Directory -Force -Path $stateDirectory | Out-Null
  [pscustomobject]@{
    sha = $sha
    lastCheckedUtc = [DateTime]::UtcNow.ToString('o')
  } | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
}

function Stop-Assistant {
  $pythonPath = Join-Path $projectDirectory '.venv\Scripts\python.exe'
  $runtimePath = Join-Path $projectDirectory 'assistant_runtime\main.py'
  if (Test-Path -LiteralPath $pythonPath -and Test-Path -LiteralPath $runtimePath) {
    & $pythonPath $runtimePath --stop | Out-Null
  }

  for ($attempt = 0; $attempt -lt 40; $attempt++) {
    if (-not (Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue)) {
      return
    }
    Start-Sleep -Milliseconds 250
  }
  throw 'A Doktor Assistant anterior nao encerrou no prazo.'
}

try {
  if (-not $Force -and (Test-Path -LiteralPath $statePath)) {
    $state = Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json
    $lastChecked = [DateTime]::Parse($state.lastCheckedUtc).ToUniversalTime()
    if (([DateTime]::UtcNow - $lastChecked).TotalHours -lt 24) {
      exit 0
    }
  }

  $headers = @{
    Accept = 'application/vnd.github+json'
    'User-Agent' = 'Doktor-Assistant-Updater'
  }
  if ($env:DOKTOR_GITHUB_TOKEN) {
    $headers.Authorization = "Bearer $($env:DOKTOR_GITHUB_TOKEN)"
  } elseif (Get-Command gh -ErrorAction SilentlyContinue) {
    $cliToken = (& gh auth token 2>$null).Trim()
    if ($cliToken) {
      $headers.Authorization = "Bearer $cliToken"
    }
  }

  $remoteSha = ''
  $localSha = ''
  $gitDirectory = Join-Path $projectDirectory '.git'
  $hasGitCheckout = (Test-Path -LiteralPath $gitDirectory) -and
    [bool](Get-Command git -ErrorAction SilentlyContinue)

  if ($hasGitCheckout) {
    Set-Location -LiteralPath $projectDirectory
    $remoteLine = (& git ls-remote origin "refs/heads/$branch" 2>$null)
    if (-not $remoteLine) {
      throw 'Nao foi possivel consultar a branch privada no GitHub usando o Git local.'
    }
    $remoteSha = (($remoteLine -split '\s+')[0]).Trim()
    $localSha = (& git rev-parse HEAD).Trim()
    if (-not $Force -and $localSha -eq $remoteSha) {
      Save-UpdateState $remoteSha
      exit 0
    }

    Write-UpdateStatus "Baixando atualizacao $($remoteSha.Substring(0, 8)) pelo Git..."
    Stop-Assistant
    & git pull --ff-only origin $branch
    if ($LASTEXITCODE -ne 0) {
      throw 'O Git nao conseguiu atualizar a copia local sem conflitos.'
    }
  } else {
    $commitApi = "https://api.github.com/repos/$repository/commits/$branch"
    $remoteCommit = Invoke-RestMethod -Uri $commitApi -Headers $headers -TimeoutSec 10
    $remoteSha = [string]$remoteCommit.sha
    if (-not $remoteSha) {
      throw 'O GitHub nao retornou o commit atual.'
    }

    if (Test-Path -LiteralPath $statePath) {
      $localSha = [string]((Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json).sha)
    }
    if (-not $Force -and $localSha -eq $remoteSha) {
      Save-UpdateState $remoteSha
      exit 0
    }

    Write-UpdateStatus "Baixando atualizacao $($remoteSha.Substring(0, 8))..."
    New-Item -ItemType Directory -Force -Path $temporaryRoot | Out-Null
    $archivePath = Join-Path $temporaryRoot 'update.zip'
    $extractPath = Join-Path $temporaryRoot 'extracted'
    $archiveUrl = "https://github.com/$repository/archive/refs/heads/$branch.zip"
    Invoke-WebRequest -Uri $archiveUrl -Headers $headers -OutFile $archivePath -TimeoutSec 60
    Expand-Archive -LiteralPath $archivePath -DestinationPath $extractPath -Force

    $sourceDirectory = Get-ChildItem -LiteralPath $extractPath -Directory | Select-Object -First 1
    if (-not $sourceDirectory) {
      throw 'O pacote baixado nao possui uma pasta de projeto.'
    }

    Stop-Assistant
    $preservedDirectories = @('.git', '.venv', 'node_modules', 'runtime')
    Get-ChildItem -LiteralPath $sourceDirectory.FullName -Force |
      Where-Object { $_.Name -notin $preservedDirectories } |
      ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $projectDirectory $_.Name) -Recurse -Force
      }
  }

  $pythonPath = Join-Path $projectDirectory '.venv\Scripts\python.exe'
  $requirementsPath = Join-Path $projectDirectory 'assistant_runtime\requirements.txt'
  if (Test-Path -LiteralPath $pythonPath) {
    & $pythonPath -m pip install --disable-pip-version-check -r $requirementsPath | Out-Null
    if ($LASTEXITCODE -ne 0) {
      throw 'Nao foi possivel atualizar os componentes de voz.'
    }
    & $pythonPath (Join-Path $projectDirectory 'assistant_runtime\create_icon.py') | Out-Null
  }

  if (Get-Command npm -ErrorAction SilentlyContinue) {
    Set-Location -LiteralPath $projectDirectory
    & npm install --no-audit --no-fund | Out-Null
    if ($LASTEXITCODE -ne 0) {
      throw 'Nao foi possivel atualizar a interface.'
    }
    & npm run build | Out-Null
    if ($LASTEXITCODE -ne 0) {
      throw 'Nao foi possivel gerar a interface atualizada.'
    }
  }

  Save-UpdateState $remoteSha
  Write-UpdateStatus 'Atualizacao concluida.'
} catch {
  if (-not $Silent) {
    Write-Error $_
  }
  exit 1
} finally {
  if (Test-Path -LiteralPath $temporaryRoot) {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force -ErrorAction SilentlyContinue
  }
}

if ($Restart) {
  $launcher = Join-Path $projectDirectory 'INICIAR_ASSISTENTE.vbs'
  Start-Process -FilePath (Join-Path $env:WINDIR 'System32\wscript.exe') `
    -ArgumentList @('//nologo', $launcher, 'open') `
    -WorkingDirectory $projectDirectory `
    -WindowStyle Hidden
}
