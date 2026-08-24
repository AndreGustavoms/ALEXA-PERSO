# Auditoria inicial do pipeline de voz

Baseline estabelecido em 2026-08-24 sobre a versao 1.4.3.

## Captura

- API: `sounddevice.RawInputStream`/PortAudio em `assistant_runtime/main.py`.
- Formato: PCM assinado de 16 bits, mono, callbacks de 30 ms.
- Sample rate: 16 kHz no modo local; 48 kHz quando OpenAI Realtime e o provider
  principal, com downsample para 24 kHz no envio.
- Transporte: callback nao bloqueante para `queue.Queue`; processamento ocorre na
  thread de audio do runtime. A API/interface HTTP e o verificador de atualizacao
  usam threads separadas.
- O Realtime usa WebSocket somente depois da wake word. Nenhuma chave OpenAI
  estava configurada no baseline.

## Processamento

- `AudioPreprocessor`: AGC limitado, alvo RMS 0.055, ganho maximo 10x, limitador
  de pico em 0.92 e noise floor adaptativo. Nao existe noise gate que descarte
  quadros; o noise floor influencia apenas o ganho.
- Pre-roll circular: 750 ms.
- VAD principal: Silero v6 ONNX, threshold 0.38 e release 0.24.
- Fallback VAD: WebRTC, agressividade 0.
- Inicio: minimo de 60 ms de fala; timeout inicial de 12 s.
- Possivel fim: 300 ms. Fim efetivo: 1.5 s de silencio + 240 ms de padding.
- Frase sem limite absoluto; watchdog de seguranca em 45 s.

## Wake/STT

- Wake provider: adaptador openWakeWord pronto, mas sem modelo portugues
  `ola_doktor.onnx`; baseline efetivo usa gramatica Vosk local.
- STT local: Vosk small pt 0.3.
- STT opcional: OpenAI Realtime `gpt-4o-transcribe`, Semantic VAD low, Vosk
  espelhado como fallback sem perda do audio ja capturado.
- Vocabulário: arquivo estatico mais nomes dos aplicativos visiveis.

## Maquina do benchmark

- CPU: AMD Ryzen 5 3600, 6 nucleos/12 threads.
- RAM: 16 GB.
- GPU: NVIDIA GTX 750 Ti, 4 GB; CUDA moderna para faster-whisper nao presumida.
- Disco livre no inicio: 405.5 GB.
- Faster Whisper deve usar CPU/int8 e modelo pequeno; OpenAI nao sera chamado
  sem chave explicitamente configurada.

## Fontes locais

- `Vozes benchmark/Gravacao.m4a`: AAC mono 48 kHz, 63.573 s.
- `Vozes benchmark/Gravacao (2).m4a`: AAC mono 48 kHz, 22.443 s.
- Os arquivos pessoais e todos os WAV derivados permanecem ignorados pelo Git.
