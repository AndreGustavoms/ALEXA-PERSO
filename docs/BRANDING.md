# Identidade Doktor Assistant

O Doktor Assistant usa a marca oficial do ecossistema Doktor: o monograma
`!D`, azul sobre fundo `#050914` nos ícones de aplicativo e transparente na
interface. A fonte visual é o repositório público
[`AndreGustavoms/Doktor.com`](https://github.com/AndreGustavoms/Doktor.com).

## Fontes de verdade

- `public/doktor-mark.svg`: marca vetorial usada na interface;
- `assets/doktor-assistant.png`: ícone mestre de 512 px para desktop;
- `assistant_runtime/create_icon.py`: gera `.ico` e artes do instalador;
- `public/site.webmanifest`: identidade instalável da interface web.

O build desktop sempre executa `create_icon.py`, evitando que executável,
instalador, tray e atalhos fiquem com versões diferentes da marca.

## Canais cobertos

- favicon SVG, PNG e ICO;
- Apple touch icon e manifest 192/512;
- cabeçalho, estado vazio e painel de voz;
- bandeja do sistema;
- executável, atalhos e desinstalador;
- instalador Windows;
- pacotes e atalhos Linux.
