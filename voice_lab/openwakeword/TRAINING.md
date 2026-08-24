# Wake word: Ola Doktor

O runtime ja possui um `OpenWakeWordEngine`, mas a producao continua no fallback
Vosk enquanto `ola_doktor.onnx` e os modelos de features nao existirem.

O treino nao deve ocorrer na venv principal. A configuracao `ola_doktor.yml` e um
ponto de partida para o pipeline oficial em Linux/Colab, com fala sintetica,
ruidos e hard negatives. Antes de promover um modelo, grave positivos e negativos
rotulados e execute `benchmark_wake.py` para medir recall, FRR e FAR.

Bloqueios desta sessao:

- os dois audios existentes nao indicam quais trechos contem a wake word;
- nao ha conjunto negativo com duracao suficiente para falsos positivos por hora;
- nao existe modelo customizado `ola_doktor.onnx` para comparar;
- o pipeline moderno de treino tem dependencias Linux/GPU e nao deve contaminar o app.

Por isso nenhum threshold ou provider de producao foi trocado sem evidencia.
