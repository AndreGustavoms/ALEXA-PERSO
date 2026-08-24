# Doktor Voice Lab - Relatorio final

Data: 2026-08-24. Baseline: Doktor 1.4.3.

## Baseline

Dataset disponivel: 2 WAVs privados, mono PCM16/16 kHz, 86.016 s no total.
Os arquivos misturam comandos e monologo e nao possuem transcricao humana nem
rotulos de wake/intencao. Por isso as metricas supervisionadas abaixo nao foram
calculadas.

| Metrica | Resultado |
| --- | ---: |
| Wake Recall | N/A - zero amostras rotuladas |
| Low Voice Recall | N/A - condicao nao rotulada |
| Normal Voice Recall | N/A - condicao nao rotulada |
| Speech Cut Rate | N/A - sem texto esperado |
| STT Accuracy / WER | N/A - sem texto esperado |
| Intent Accuracy | N/A - sem intencao esperada |
| End-to-End Accuracy | N/A - sem intencao/entidade esperadas |
| VAD boundary-risk proxy | 0/2 segmentos (0%) |
| Vosk mean latency | 8,194.73 ms por arquivo |
| Vosk mean realtime factor | 0.2067x |

Sinal observado: RMS bruto 0.01155 nos dois arquivos, picos 0.1201 e 0.1480,
noise floor final aproximado de 0.00118, ganho final 10x e clipping processado 0%.
O Silero processou o audio em 0.0287x do tempo real.

## Experimentos controlados

Foram executadas 21 configuracoes, sempre alterando uma familia por vez.

| Familia | Resultado medido |
| --- | --- |
| VAD | Silero e WebRTC capturaram 99.99%; WebRTC nao demonstrou ganho funcional |
| Pre-roll | 300 ms: 99.23%; 400 ms: 99.50%; 600 ms: 99.89%; 800/1000 ms: 99.99% |
| End padding | 120/240/400/600 ms: sem diferenca nestes arquivos |
| Hangover | 900 ms dividiu em 3 turnos; 1200 ms ou mais manteve 2 turnos |
| Ganho | 1x: 99.64%; 4/7x: 99.71%; 10x: 99.99%; clipping 0% em todos |
| Noise gate | Nao existe gate destrutivo no pipeline; teste nao aplicavel |

O proxy de borda usa energia nos primeiros/ultimos 120 ms. Ele ajuda a localizar
segmentos suspeitos, mas nao substitui Speech Cut Rate com texto esperado.

## STT A/B

`faster-whisper` 1.2.1, modelo `base`, CPU/int8, foi instalado em venv isolada.
Nao foi adicionado ao app nem ao instalador.

| Provider | Arquivo 1 | Arquivo 2 | Mean RTF |
| --- | ---: | ---: | ---: |
| Vosk small pt 0.3 | 0.1729x | 0.2405x | 0.2067x |
| faster-whisper base | 0.2735x | 0.1058x | 0.1897x |

Observacao nao supervisionada: Whisper produziu `YouTube`, `Valorante`, `Google`
e frases coerentes; Vosk produziu, entre outros, `valor antes`. Isso e evidencia
promissora para um proximo A/B rotulado, nao uma medida de acuracia.

OpenAI transcription: **nao executado**. Nenhuma chave estava configurada e
nenhum audio foi enviado para servicos externos.

## Wake word

Provider ativo: `vosk-fallback`. O primeiro arquivo provocou deteccao a partir de
4.2 s; o segundo nao provocou deteccao. Esses resultados nao contam como acerto ou
erro porque os arquivos nao possuem `expected_wake`.

openWakeWord: **nao executado**. O adaptador existe, mas nao ha
`ola_doktor.onnx`, conjunto positivo/negativo rotulado nem duracao negativa para
calcular falsos positivos por hora. Treinar na maquina principal foi rejeitado
para nao misturar dependencias antigas/Linux/GPU com o Doktor.

## Best Configuration

A melhor configuracao defensavel e a baseline atual:

```json
{
  "vad_engine": "silero",
  "pre_roll_duration": 0.75,
  "speech_end_silence": 1.5,
  "end_padding_duration": 0.24,
  "maximum_input_gain": 10.0
}
```

As metricas supervisionadas da melhor configuracao continuam N/A. Nenhuma
alteracao de producao foi promovida sem comprovacao.
O score ponderado tambem ficou N/A: a funcao recusa pontuar configuracoes sem
End-to-End Accuracy, Low/Normal Recall, Speech Cut, Wake, false wake e latencia.

## Difference

- Nenhuma regressao de configuracao foi introduzida.
- Pre-roll menor que 600 ms foi descartado por perder audio mensuravel.
- Hangover de 900 ms foi descartado por separar uma pausa presente no dataset.
- Ganho 10x foi mantido: maior cobertura observada, sem clipping nestes arquivos.
- faster-whisper ficou como provider experimental ate existir dataset rotulado.

## Falhas restantes

### Arquivo 1

Expected: N/A. Vosk: `abre o valor antes`. Whisper: `Abre o Valorante`.
Likely cause: limite lexical/acustico do modelo Vosk; requer rotulo para confirmar.

### Wake word

Expected: N/A. Vosk detectou repetidamente a mesma hipotese parcial apos 4.2 s.
Likely cause: o contador bruto do lab observa a mesma parcial em varios frames;
o runtime real muda de estado na primeira deteccao.

## Changes Recommended

1. Usar o gravador guiado para criar 3-5 amostras por frase/condicao com rotulo.
2. Reexecutar baseline, grid controlado e A/B Whisper no mesmo dataset.
3. Promover faster-whisper somente se elevar End-to-End Command Accuracy sem
   exceder os limites de CPU/RAM e latencia.
4. Treinar `ola_doktor.onnx` em Colab/Linux isolado com fala sintetica, varias
   vozes, ruido e hard negatives; calibrar threshold com as gravacoes locais.
5. Manter audios, manifests locais e resultados detalhados fora do Git.

## Reprodutibilidade e privacidade

Ferramentas: `benchmark.py`, `experiments.py`, `benchmark_whisper.py`,
`benchmark_wake.py`, `record_samples.py` e `delete_private_dataset.py`.
O replay passa por VAD, STT, normalizador e parser, mas nunca chama executores.
Audios pessoais, ambientes de modelo e resultados brutos estao no `.gitignore`.
