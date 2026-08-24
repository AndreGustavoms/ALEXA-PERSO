# Benchmark de voz do Doktor

Este documento registra a bateria local executada em 24/08/2026. O objetivo foi
medir o caminho real do aplicativo: captura, preprocessamento, VAD, wake word,
STT e parser. Nenhuma acao do computador foi executada durante os testes.

## Resultado selecionado

| Cenario | Resultado |
| --- | ---: |
| Wake recall | 100% |
| Falsos positivos da wake word | 0% |
| Reconhecimento de intencao | 100% no corpus NLU |
| Reconhecimento de entidade | 100% no corpus NLU |
| Vosk end-to-end limpo | 88,89% |
| Vosk end-to-end com volume/ruido | 85% |
| Latencia media do Vosk | 1,41 s |

O Vosk foi mantido como engine padrao porque entrega o melhor equilibrio entre
precisao, latencia, memoria e funcionamento offline. O faster-whisper fica
disponivel apenas como experimento do Voice Lab: no conjunto testado, o modelo
small foi mais pesado e nao melhorou o resultado limpo.

## Comportamento da captura

1. O microfone fica em modo de espera e procura somente `Ola, Doktor`.
2. A deteccao exige dois frames consecutivos e ignora candidatos no meio de
   uma fala continua, reduzindo ativacoes acidentais.
3. Apos a ativacao, o pre-roll preserva o inicio do comando e o VAD aceita voz
   baixa sem exigir que a pessoa grite.
4. O turno termina depois de aproximadamente 1,5 segundo de silencio continuo.
   Nao existe limite curto enquanto a pessoa ainda esta falando.
5. O runtime volta para o modo de espera depois de processar o comando. Ele nao
   continua transcrevendo a conversa seguinte sem outra wake word.

Os valores ajustaveis ficam em `assistant_runtime/voice_config.json`. Para
headset, use o perfil `near_field`; para microfone distante, use `far_field` em
`assistant_runtime/stt_config.json`.

## Nomes e comandos

O parser normaliza acentos, pontuacao e variacoes de fala. Entre os aliases
testados estao `valorant`, `valorante` e `valor`, que apontam para o mesmo
aplicativo. Para acrescentar um programa ou nome recorrente, inclua o termo em
`assistant_runtime/transcription_vocabulary.txt` e registre a acao no parser.

Exemplos:

```text
Ola, Doktor, abra o Valorant
Ola, Doktor, abre o WhatsApp
Ola, Doktor, pesquisa futebol no YouTube
```

## Reproduzir os testes

Os arquivos de audio autorizados, recortes e manifests locais sao ignorados
pelo Git. Com o ambiente de desenvolvimento instalado:

```powershell
.\.venv\Scripts\python.exe -m voice_lab.prepare_existing_dataset
.\.venv\Scripts\python.exe -m voice_lab.augment_dataset
.\.venv\Scripts\python.exe -m voice_lab.benchmark_wake --manifest voice_lab/manifests/local-dataset.jsonl
.\.venv\Scripts\python.exe -m voice_lab.benchmark --manifest voice_lab/manifests/local-dataset.jsonl
python -m assistant_runtime.intent_benchmark
```

O relatorio detalhado esta em `voice_lab/reports/overnight-report.md`. O
benchmark e somente de leitura para o computador: ele importa o parser e os
detectores, mas nao chama executores de comandos.

## Diagnostico rapido

- Se nao ouvir a wake word, confira o microfone selecionado e rode o monitor:
  `python -m voice_lab.live_monitor`.
- Se cortar o inicio, aumente `pre_roll_duration` em `voice_config.json`.
- Se encerrar cedo, aumente `speech_end_silence` em pequenos passos.
- Se ativar durante conversas, mantenha o guard temporal e revise o ruido do
  ambiente antes de reduzir thresholds.
- Para inspecionar a fase atual, abra a interface local; o runtime publica VAD,
  wake score, engine, latencia e estado sem salvar audio bruto.
