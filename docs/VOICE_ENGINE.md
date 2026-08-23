# Voice Engine

Estados principais:

```text
wake -> wake_detected -> activated -> listening -> processing
     -> executing -> responding -> wake
```

O Vosk ouve localmente apenas `Ola, Doktor`. Depois da ativação, o provider
configurado recebe a fala. `auto` usa OpenAI Realtime somente quando há chave e
mantém Vosk em paralelo para fallback. O VAD local não impõe duração máxima;
silêncio contínuo encerra a frase no modo local.

O microfone pode ser trocado no onboarding/configurações. A mudança reinicia o
stream de áudio, não o aplicativo. Áudio bruto permanece em memória e não é
gravado. Apenas métricas agregadas são persistidas.
