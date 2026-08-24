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

## Detector

O pacote padrao continua com WebRTC VAD em modo 0 (`VERY_HIGH`). Ele e pequeno,
streaming e compativel com 8, 16, 32 e 48 kHz. A interface `SpeechDetector`
permite adicionar Silero ONNX futuramente sem acoplar captura, STT ou turnos. O
runtime ONNX nao foi incluido no pacote leve por causa do aumento de tamanho e
memoria.

## Diagnostico e privacidade

A API publica somente RMS bruto/processado, pico, noise floor, ganho, clipping,
decisao binaria do VAD, chunks e duracoes. Audio bruto nao e salvo. O painel fica
na configuracao do microfone e serve para diagnosticar fala baixa sem registrar
conteudo.

## Defaults conversacionais

- inicio minimo de fala: 60 ms
- possivel fim: 300 ms
- silencio antes do endpoint: 1.500 ms
- padding final: 240 ms
- pre-roll: 750 ms
- espera inicial: 12 s
- watchdog anormal: 45 s
