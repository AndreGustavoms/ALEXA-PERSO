# Empacotamento macOS

O pipeline macOS esta bloqueado pelo motor de wake word atual. O pacote `vosk
0.3.45` nao publica wheel nem source distribution para macOS no PyPI. Sem ele,
o Doktor nao consegue manter a wake word local e um DMG seria enganoso.

Quando o provider local for substituido por um motor com binarios macOS, o
runtime, `MacOSAdapter`, caminhos de Application Support, Keychain via
`keyring`, menu bar e LaunchAgent ja possuem as fronteiras necessarias para
adicionar jobs `macos-15-intel` e `macos-latest`. Nao publique DMG antes de um
teste real de wake word, microfone, assinatura e notarizacao em ambos os chips.
