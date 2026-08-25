# Pipeline de voz

## Auditoria

O corte de comandos acontecia entre a wake word e o STT. O runtime reproduzia
"Sim, pode falar" de forma bloqueante e depois esvaziava a fila do microfone.
Comandos imediatos eram descartados. O ganho por frame tambem elevava ruido como
se fosse voz e o endpoint encerrava depois de apenas 0,9 segundo de silencio.

## Fluxo atual

`RawInputStream` e o unico proprietario do microfone. Cada frame PCM mono passa
por `AudioPreprocessor`, segue para um buffer circular e e entregue ao detector
de wake word ou, durante um turno, a `TurnManager` e ao STT.

O `TurnManager` usa os estados `WAITING`, `POSSIBLE_SPEECH`, `ACTIVE_SPEECH`,
`POSSIBLE_END` e `ENDED`. O fim normal depende do VAD, do silencio conversacional
e do padding. O watchdog de 45 segundos existe apenas para recuperar um turno
preso.

Ao detectar "Ola, Doktor", o STT e criado antes do bip e recebe 750 ms de
pre-roll. Assim, "Ola, Doktor abre o Chrome" e o comando dito depois do bip usam
o mesmo stream sem perder o inicio.

## Detectores

Silero VAD v6 roda pelo modelo ONNX oficial, sem Torch ou Torchaudio. O wrapper
mantem estado streaming, converte 32/48 kHz para 16 kHz e publica o score real.
WebRTC VAD em modo 0 (`VERY_HIGH`) permanece como fallback para arquiteturas sem
ONNX Runtime.

O binario `assistant_runtime/models/silero_vad.onnx` (2.327.524 bytes, ~2,22 MB)
e a versao oficial do Silero VAD v6, licenciada MIT pelo Silero Team
(`licenses/SILERO-VAD-LICENSE.txt`). Checksum SHA-256 do arquivo commitado:

```
1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3
```

`packaging/doktor.spec` valida, antes de empacotar, que o modelo e o arquivo de
licenca existem; `assistant_runtime/tests/test_model_assets.py` reproduz esse
checksum em teste automatizado para detectar substituicao ou corrupcao do
arquivo.

`WakeWordEngine` tenta carregar openWakeWord 0.6.0 somente quando o modelo
`ola_doktor.onnx` e os modelos de features estao presentes. Ate o modelo
portugues ser treinado e avaliado, o Vosk local continua como fallback. Nesse
fallback nao existe score de confianca e a API retorna `null`.

## Diagnostico e privacidade

A API publica somente RMS bruto/processado, pico, noise floor, ganho, clipping,
score do Silero, engine/score da wake word, chunks e duracoes. Audio bruto nao e
salvo. O Voice Lab serve para diagnosticar fala baixa sem registrar conteudo.

O manifesto de avaliacao fica em `voice_lab/evaluation_manifest.json`, e a
configuracao inicial de treinamento em `voice_lab/openwakeword/ola_doktor.yml`.

## Defaults conversacionais

- inicio minimo de fala: 60 ms
- possivel fim: 300 ms
- silencio antes do endpoint: 1.500 ms
- padding final: 240 ms
- pre-roll: 750 ms
- espera inicial: 12 s
- watchdog anormal: 45 s
