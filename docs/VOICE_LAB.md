# Voice Lab

O Voice Lab exibe dados produzidos pelo backend, sem animacao simulada:

- RMS bruto e processado;
- pico, noise floor, ganho e clipping;
- probabilidade e estado do Silero VAD;
- score e threshold do wake provider quando disponiveis;
- duracao de fala, silencio e buffer;
- engine de wake word e VAD realmente carregados;
- rastreamento completo da ultima intencao.

O audio bruto permanece apenas em memoria. O projeto nao grava amostras sem uma
funcao futura de replay explicitamente habilitada pelo usuario.
