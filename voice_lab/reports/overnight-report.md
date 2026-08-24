# Doktor Overnight Voice Benchmark

Data: 2026-08-24. Commit inicial: `ce16fc3`. Execucao: dry-run local.

## Resumo executivo

| Metrica | Antes | Depois |
| --- | ---: | ---: |
| Wake Recall | 100% | 100% |
| False Accept Rate | 20% | 0% |
| Low Voice End-to-End | 100% | 100% |
| Speech Cut Rate | 22.22% | 22.22% |
| STT WER | 22.22% | 22.22% |
| Intent Accuracy | 88.89% | 88.89% |
| Entity Accuracy | 83.33% | 100% |
| End-to-End Accuracy | 77.78% | 88.89% |
| Holdout End-to-End | 50% | 75% |
| Mean Vosk STT latency | 1,411.58 ms | 1,414.54 ms |

O ganho veio de duas mudancas isoladas: protecao temporal da wake word e
normalizacao segura de entidade/pontuacao. Nenhum threshold de microfone foi
reduzido.

Score ponderado final: **0.8987**, usando latency score linear ate 3 s e os pesos
30/20/15/10/10/5/5/5 definidos na missao.

## Hardware

- AMD Ryzen 5 3600, 6 cores/12 threads.
- 16 GB RAM.
- NVIDIA GTX 750 Ti, 4 GB; benchmarks Whisper executados em CPU/int8.
- Mais de 400 GB livres no inicio da bateria.

## Dataset

- 2 M4A autorizados, 86.016 s no total.
- 10 recortes identificaveis da gravacao de comandos.
- 1 arquivo de fala continua usado como negativo de acao/wake.
- 30 variacoes deterministicas: volume 50%, 35%, 25% e ruido branco 20/10 dB.
- Seed: `20260824`.
- Calibration, validation e holdout separados antes das mudancas.
- Audios, hashes e manifests com caminhos pessoais permanecem fora do Git.

Os textos dos recortes foram inferidos por consenso entre Vosk, Whisper base,
Whisper small e as pausas do arquivo. Eles estao marcados
`local_stt_consensus_needs_human_audit`; nao sao apresentados como transcricao
humana perfeita.

## Baseline

O primeiro runner enviava WAV bruto ao Vosk. A auditoria descobriu que producao
envia audio apos `AudioPreprocessor`; o runner foi corrigido antes da selecao.

Baseline fiel a producao:

- WER 22.22%; CER 18.52%.
- Intent 88.89%; Entity 83.33%; End-to-End 77.78%.
- Start Cut 11.11%; End Cut 11.11%.
- 11/11 segmentos detectados pelo VAD.
- Zero clipping.

## Experiments Run

- 21 configuracoes VAD/pre-roll/padding/hangover/gain no audio original.
- As mesmas 21 configuracoes nas 30 variacoes de robustez.
- Vosk bruto vs Vosk com preprocessing de producao.
- faster-whisper 1.2.1: `base` e `small`, CPU/int8.
- Whisper small beam 5 vs greedy/beam 1.
- Wake Vosk parcial antes/depois de guard temporal.
- Normalizacao, entidades, negativos e corpus NLU de 124 frases.

## Top Configurations

| Candidato | Clean E2E | Robustness E2E | Latencia curta | Decisao |
| --- | ---: | ---: | ---: | --- |
| Vosk + AGC + aliases finais | 88.89% | 85% | 1.41 s | vencedor leve |
| Whisper small/int8 | 88.89% | 100% | 2.74 s | experimental |
| Whisper base/int8 | 66.67% | 70% | 0.72-0.87 s | rejeitado |

Whisper small nao superou o Vosk no conjunto clean/holdout e aumentou latencia e
tamanho. Ele permanece ferramenta A/B isolada, nao dependencia do aplicativo.

## Wake Results

Antes: recall 100%, FAR 20%. Um comando `abrir o YouTube` e a fala continua
geravam hipotese parcial falsa.

Depois: recall 100%, FRR 0%, FAR 0%, primeira deteccao em 1.11 s. O fallback
agora exige os dois frames consecutivos ja configurados e rejeita candidato que
surge tarde numa fala continua. O VAD real alimenta esse guard.

openWakeWord nao foi executado: nao existe `ola_doktor.onnx`. Nenhum resultado
foi inventado e o fallback atual nao foi removido.

## VAD Results

- Silero e WebRTC detectaram todos os 30 samples de robustez.
- Silero baseline capturou 99.47% do audio, RTF 0.0292x.
- Pre-roll de 300 ms caiu para 98.84%; 750 ms foi mantido.
- Padding 120-600 ms nao alterou este dataset.
- Hangover 900-2100 ms nao alterou os recortes; no arquivo longo, 900 ms ja
  havia dividido indevidamente um turno.
- Gain 1-10x nao gerou clipping; 10x foi mantido pela curva de voz baixa.

## STT Results

| Provider | Clean WER | Clean E2E | Robust E2E | Mean RTF robust |
| --- | ---: | ---: | ---: | ---: |
| Vosk production | 22.22% | 88.89% | 85% | 0.4888x |
| Whisper base raw | 48.89% | 70% | 70% | 0.4005x |
| Whisper small raw | 42.59% | 88.89% | 100% | 1.2301x |

WER penaliza flexoes como `abrir`/`abre`; End-to-End mede a acao planejada e e
a metrica principal. O Whisper small resistiu melhor a 10 dB, mas nao venceu o
holdout clean e foi mais lento.

## NLU Results

- Corpus textual: 124/124 intent, 100% entity, 0% false positive negativo.
- `valorante` e a hipotese Vosk `valor` agora resolvem `valorant` somente dentro
  de um comando explicito de aplicativo.
- Pontuacao terminal de STT e removida antes do parser; URLs internas permanecem.
- Formas narrativas `abriu` e `desligo` nao foram convertidas em imperativos por
  seguranca.

## Low Voice Results

Nas 18 variantes de volume 50/35/25, o Vosk com AGC detectou 18/18; nas 12 com
rotulo de acao obteve 100% End-to-End. A necessidade de gritar nao se reproduziu no replay apos o
preprocessing correto. O monitor ao vivo continua necessario para validar o
dispositivo fisico e ganho do Windows.

## Cut-off Results

- `fecha o YouTube` virou `fechar o YouTube`: significado preservado.
- `abre o Valorant` virou `abre o valor`: classificado END_CUT, entidade
  recuperada com alias comprovado.
- `desliga o computador` virou `o computador`: START_CUT e falha restante.
- Nenhuma das 30 variantes de volume/ruido sofreu start/end cut apos AGC.

## Latency And Resources

- VAD Silero: aproximadamente 2.9% de um core em replay acelerado (RTF 0.029).
- Vosk: RTF 0.475 clean e 0.489 robust.
- Whisper small: RTF 1.082 clean e 1.230 robust; cerca de 2.1-2.7 s por comando
  curto nesta CPU.
- Nenhum processo de benchmark ficou em segundo plano.
- OpenAI nao foi chamado; nenhuma chave estava configurada.

## Error Taxonomy

Falhas finais observadas, sem duplicar artificialmente para chegar a 20:

1. `VAD_START_MISS/STT_ERROR`: shutdown -> `o computador`.
2. `STT_ERROR`: YouTube a 10 dB -> `outubro`.
3. `STT_ERROR`: Google a 10 dB -> apenas `o`.
4. `STT_ERROR`: console a 10 dB -> `consorcio`.
5. `NEEDS_USER_SAMPLE`: nao ha repeticoes reais LOW/FAR/FAST por frase.
6. `NEEDS_USER_SAMPLE`: um unico positivo de wake nao estima variancia real.
7. `NEEDS_MODEL`: openWakeWord customizado ausente.

## Recommended Changes

Aplicadas:

- guard de wake por frames consecutivos + duracao da fala;
- pontuacao terminal segura;
- aliases `valorante` e `valor` para Valorant;
- benchmark fiel ao AGC de producao;
- dataset curado/augmentado, CER, split e action labels.

Rejeitadas:

- reduzir pre-roll, hangover ou thresholds;
- mapear `outubro` para YouTube e `consorcio` para console, por overfit ao ruido;
- transformar `desligo` em `desliga`, por risco de executar fala narrativa;
- embarcar Whisper small agora, por empate clean, maior latencia e peso.

## Reproducibilidade

```powershell
.\.venv\Scripts\python.exe -m voice_lab.prepare_existing_dataset
.\.venv\Scripts\python.exe -m voice_lab.augment_dataset
.\.venv\Scripts\python.exe -m voice_lab.benchmark --manifest voice_lab/manifests/local-curated.jsonl
.\.venv\Scripts\python.exe -m voice_lab.benchmark_wake --manifest voice_lab/manifests/local-curated.jsonl
```

Todos os caminhos de benchmark terminam em parser/action plan. Nenhum executor de
Windows e chamado.

## Regression Suite

- 203 testes do runtime: PASS.
- 6 testes do Voice Lab: PASS.
- Corpus NLU 124 frases: 100% intent, 100% entity, 0% negative FP.
- ESLint: PASS.
- TypeScript + Vite build: PASS.
- 50 repeticoes do mesmo audio: uma unica transcricao, deterministico.
