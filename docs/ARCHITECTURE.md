# Arquitetura

O Doktor mantém a arquitetura existente: React/Vite gera arquivos estáticos e
um único processo Python serve interface/API, tray, voz e comandos. Node nao
faz parte do aplicativo instalado.

```text
Microfone -> wake Vosk local -> VAD -> STT provider
          -> IntentParser -> CommandRouter -> PlatformAdapter -> acao registrada
          -> TTS -> wake
```

`assistant_runtime/app_paths.py` separa recursos imutáveis do pacote dos dados
do usuário. Configurações, permissões, métricas e logs nunca são escritos na
pasta de instalação.

`VERSION` é a fonte de versão. `packaging/doktor.spec` inclui frontend, assets,
modelo e dependências nativas. O app opera com privilégio do usuário atual.

O texto transcrito nunca é entregue a shell. O registro declarativo define
intenções, parâmetros, risco, confirmação e executor permitido.
