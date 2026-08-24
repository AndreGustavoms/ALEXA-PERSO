# Doktor Voice Lab

Laboratorio offline para medir o pipeline real sem executar comandos no computador.
Audios, manifests locais e resultados detalhados ficam ignorados pelo Git.

## Monitor ao vivo

```powershell
.\.venv\Scripts\python.exe -m voice_lab.live_monitor
```

Mostra sinal bruto/processado, noise floor, clipping, wake score, VAD, estado,
parcial/final e latencia. O caminho de execucao de acoes nao e importado.

## Gravar dataset rotulado

```powershell
.\.venv\Scripts\python.exe -m voice_lab.record_samples --list
.\.venv\Scripts\python.exe -m voice_lab.record_samples --condition NORMAL_VOICE
```

## Executar baseline e experimentos

```powershell
.\.venv\Scripts\python.exe -m voice_lab.benchmark --manifest voice_lab/manifests/local-dataset.jsonl
.\.venv\Scripts\python.exe -m voice_lab.experiments --manifest voice_lab/manifests/local-dataset.jsonl
```

O replay mede sinal, VAD, segmentos, Vosk e parser, mas nunca chama executores.
WER, Speech Cut Rate e acuracia end-to-end ficam `null` para audio sem rotulo.

## Comparar faster-whisper

O provider opcional fica em uma venv separada para nao aumentar o aplicativo:

```powershell
python -m venv voice_lab/.venv-whisper
.\voice_lab\.venv-whisper\Scripts\pip.exe install -r voice_lab/requirements-whisper.txt
.\voice_lab\.venv-whisper\Scripts\python.exe -m voice_lab.benchmark_whisper --manifest voice_lab/manifests/local-dataset.jsonl --model base
```

O modelo `base` usa CPU/int8. O benchmark nao envia audio para servicos externos.

## Wake word

```powershell
.\.venv\Scripts\python.exe -m voice_lab.benchmark_wake --manifest voice_lab/manifests/local-dataset.jsonl
```

Cada registro deve ter `expected_wake: true` ou `false`. Sem esse rotulo, Wake
Recall, False Reject Rate e False Accept Rate permanecem `null`.

## Privacidade

```powershell
.\.venv\Scripts\python.exe -m voice_lab.delete_private_dataset --yes
```

Nenhum audio e enviado para a rede. Providers externos devem ser habilitados e
autorizados explicitamente em ferramentas separadas.
