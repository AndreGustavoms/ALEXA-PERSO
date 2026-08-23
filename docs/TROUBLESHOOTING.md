# Troubleshooting

## O assistente não acorda

Abra Configurações, escolha o microfone correto e confirme movimento no nível
de entrada. Diga `Ola, Doktor`, aguarde o bip e só então fale o comando.

## Microfone indisponível

Confira a permissão de microfone do sistema e feche programas com acesso
exclusivo ao dispositivo. O Doktor tenta reconectar automaticamente.

## Diagnóstico

Com o app aberto, `http://127.0.0.1:3000/api/health` informa microfone, wake
word, STT, TTS, rede, provider, adapter e updates. Logs ficam em:

- Windows: `%LOCALAPPDATA%\Doktor Assistant\logs`
- macOS: `~/Library/Application Support/Doktor Assistant/logs`
- Linux: `$XDG_DATA_HOME/doktor-assistant/logs`

Logs não contêm chave, token ou áudio. Para falhas de update, compare o asset
com `SHA256SUMS` na mesma GitHub Release.
