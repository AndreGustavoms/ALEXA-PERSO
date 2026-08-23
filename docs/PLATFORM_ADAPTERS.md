# Platform Adapters

`platforms/factory.py` detecta SO e arquitetura e importa somente o adapter
necessário. O core depende do protocolo `PlatformActions`, não de Win32.

- `WindowsAdapter`: todos os comandos atuais, janelas, mídia, volume e sistema.
- `LinuxAdapter`: web, pesquisa, pastas e aplicativos conhecidos.
- `MacOSAdapter`: web, pesquisa, pastas e aplicativos conhecidos.

Cada adapter recebe uma `ParsedIntent` validada. Novos handlers devem usar o
nome de executor registrado e validar parâmetros; não devem aceitar texto como
comando livre.

Autostart fica em `platforms/system.py`: Startup do usuário no Windows,
LaunchAgent no macOS e arquivo XDG Autostart no Linux.
