# Build

## Requisitos de desenvolvimento

- Python 3.11 ou 3.12
- Node.js 22
- Windows x64 ou Linux x64/ARM64 nativo
- Inno Setup 6 somente para o instalador Windows

O aplicativo final inclui Python, frontend, bibliotecas e modelo Vosk. Esses
requisitos existem apenas para quem gera o pacote.

## Build local

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r assistant_runtime\requirements.txt -r requirements-build.txt
npm ci
npm run build
.\.venv\Scripts\python assistant_runtime\setup_model.py
.\.venv\Scripts\python scripts\build_desktop.py --skip-web --skip-model
```

O one-folder fica em `build/pyinstaller/Doktor`. No Windows, compile
`packaging/windows/Doktor.iss`. No Linux, execute
`packaging/linux/build-packages.sh` depois do PyInstaller.

PyInstaller nao faz cross-compilation: gere cada pacote no SO e arquitetura de
destino. O workflow aplica essa regra.

## Matriz atual

| Plataforma | Pacotes | Estado |
| --- | --- | --- |
| Windows x64 | EXE | suportado e validado |
| Linux x64 | AppImage, DEB | suportado no CI |
| Linux ARM64 | AppImage, DEB | suportado no CI |
| Windows ARM64 | - | bloqueado pelo wheel Vosk |
| macOS Intel/ARM64 | - | bloqueado pelo Vosk 0.3.45 no PyPI |

Nao adicione uma plataforma a release antes de validar wake word, captura,
tray, autostart, instalacao e desinstalacao no hardware correspondente.
