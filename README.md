# Doktor Assistant

Assistente local do ecossistema Doktor para Windows. Permanece em segundo plano, reconhece uma frase de
ativacao sem enviar o audio para um servidor e responde usando a voz instalada
no computador.

## Instalar

De dois cliques em `INSTALAR_ASSISTENTE.cmd`.

O instalador prepara o ambiente Python, baixa o modelo de portugues, instala a
interface, cria o atalho `Doktor Assistant` na area de trabalho e configura o
inicio automatico com o Windows. Depois disso, o aplicativo fica disponivel no
icone da bandeja do sistema.

## Usar

1. Diga `Ola, Doktor`.
2. Aguarde o sinal sonoro.
3. Comece a falar em ate sete segundos.
4. Depois que a fala comeca, nao existe limite de duracao.
5. Dois segundos de silencio continuo encerram o comando.

A frase anterior, `Ola, assistente`, continua aceita como alias de compatibilidade.

Na primeira abertura, selecione `Autorizar comandos`, leia o termo local e
marque a confirmacao. A autorizacao fica salva somente neste computador e pode
ser revogada pela mesma tela.

Exemplos implementados:

- `Abra o YouTube`, `entre no GitHub` ou `pesquise musica brasileira`.
- `Abra o Chrome`, `abra a calculadora` ou `abra o VS Code`.
- `Nova aba`, `atualiza`, `volta` ou `feche esta pagina`.
- `Minimize isso`, `mostre a area de trabalho` ou `vai pra outra janela`.
- `Volume 35`, `aumente o volume`, `pause` ou `proxima musica`.
- `Escreve meu nome aqui` ou `aperta Enter` na janela em foco.
- `Abra Downloads`, `abra o Bluetooth` ou `tira um print`.
- `Que horas sao?`, `qual a data` ou `que dia da semana e hoje?`.
- `Desligue o computador` pede confirmacao antes de agir.

`Feche esta pagina` fecha somente a aba atual quando um navegador esta em
foco. `Feche o Chrome` e uma intencao diferente, direcionada ao aplicativo
inteiro, e exige confirmacao porque pode haver trabalho nao salvo.

Fechar a interface nao encerra o assistente. Use o icone na bandeja para abrir
a interface, pausar a escuta, ativar ou desativar o inicio com o Windows e
encerrar completamente.

O inicializador mantem somente um processo permanente do assistente. Abrir o
atalho novamente apenas mostra a interface existente. Instalacoes e atualizacoes
pedem ao icone da bandeja para encerrar de forma graciosa antes de iniciar a
nova versao, evitando processos e icones duplicados.

O atalho da area de trabalho e `INICIAR_ASSISTENTE.cmd` abrem a interface em
uma janela local do Chrome ou Edge. A pagina tambem fica disponivel em
`http://localhost:3000` enquanto o aplicativo estiver ativo.

## Arquitetura

- `assistant_runtime/`: reconhecimento continuo com Vosk, sintese de voz,
  bandeja do Windows e servidor HTTP local.
- `assistant_runtime/commands.py`: fachada compativel para o nucleo de comandos.
- `assistant_runtime/assistant_commands/models.py`: contratos, riscos e resultados.
- `assistant_runtime/assistant_commands/registry.py`: registro declarativo de comandos.
- `assistant_runtime/assistant_commands/parser.py`: aliases, contexto e parametros.
- `assistant_runtime/assistant_commands/context.py`: janela e processo em foco.
- `assistant_runtime/assistant_commands/actions.py`: acoes Windows autorizadas.
- `assistant_runtime/assistant_commands/confirmation.py`: confirmacao com expiracao.
- `assistant_runtime/assistant_commands/history.py`: ultimas 20 interacoes em memoria.
- `assistant_runtime/permission_store.py`: consentimento local persistente.
- `assistant_runtime/voice_activity.py`: VAD, inicio e fim dinamicos da fala.
- `assistant_runtime/voice_config.json`: parametros editaveis da captura de voz.
- `App.tsx`, `components/` e `app/globals.css`: interface responsiva em React.
- `hooks/`: integracoes isoladas com o runtime local e APIs de voz do navegador.
- `lib/`: respostas iniciais e mensagens de erro.
- `scripts/install-assistant.ps1`: instalacao, build, atalho e inicializacao.
- `runtime/`: modelo e logs gerados localmente, fora do Git.

O runtime usa duas etapas: uma gramatica pequena fica ouvindo apenas a frase de
ativacao; depois do sinal sonoro, o reconhecedor completo e o WebRTC VAD captam
o comando. O prazo vale apenas para iniciar a fala. Depois disso, o VAD tolera
pausas naturais e encerra somente apos silencio continuo, sem duracao maxima.

Os valores ficam centralizados em `assistant_runtime/voice_config.json`:

```json
{
  "activation_start_timeout": 7.0,
  "speech_end_silence": 2.0,
  "minimum_speech_duration": 0.24,
  "maximum_phrase_duration": null,
  "vad_aggressiveness": 2
}
```

A permissao total vale para as acoes registradas e para os privilegios da conta
atual do Windows. Ela nao ignora o UAC. Desligamento, reinicio, encerramento de
sessao, suspensao, hibernacao, fechamento explicito de aplicativo e exclusao de
item exigem `sim` antes de executar; `nao`, `cancela` ou `deixa quieto` cancelam.
A confirmacao expira em 15 segundos. Formatacao e shell arbitrario permanecem
bloqueados.

## Comandos locais

- Navegador: abrir site/URL, pesquisar, abas, historico, downloads, favoritos,
  navegacao, zoom, tela cheia e janela privada.
- Aplicativos: programas conhecidos e atalhos instalados do Menu Iniciar.
- Janelas: fechar, minimizar, maximizar, restaurar, alternar, encaixar e desktop.
- Audio e midia: volume absoluto/relativo, mudo, play/pause e troca de faixa.
- Sistema: bloquear, desligar, reiniciar, sair, suspender e hibernar.
- Arquivos: pastas conhecidas, pasta por nome inequivoco, navegacao, nova pasta,
  renomear, copiar, recortar, colar e exclusao para a Lixeira com confirmacao.
- Tela e configuracoes: capturas, brilho em hardware compativel e paginas do
  Windows para Wi-Fi, Bluetooth, som, tela, rede, armazenamento e update.
- Edicao e informacao: selecionar, desfazer, refazer, localizar, data e hora.

Os aliases sao normalizados sem diferenciar maiusculas, pontuacao ou acentos.
O parser aceita parametros como `volume 50`, `brilho 80`, consultas e URLs. Ele
nao usa aproximacao agressiva em acoes perigosas e nunca transforma a fala em
um comando livre de terminal.

Limitacoes reais: fechar outras abas ou abas a direita nao possui atalho seguro
e uniforme entre navegadores, por isso essas acoes sao recusadas. Brilho depende
do monitor expor a interface WMI. Captura da janela vai para a area de
transferencia; captura da tela com `Win+PrintScreen` vai para a pasta configurada
do Windows. Abertura de pasta por nome consulta apenas locais pessoais imediatos
e recusa resultados ausentes ou ambiguos.

A interface e gerada como arquivos estaticos pelo Vite e servida pelo mesmo
processo Python. O Node.js e usado apenas na instalacao e no desenvolvimento;
ele nao permanece aberto enquanto o assistente trabalha em segundo plano.

## Desenvolvimento

```powershell
npm install
npm run dev
```

Para executar o runtime com logs visiveis:

```powershell
npm run assistant:console
```

Para encerrar a instancia em segundo plano sem forcar o processo:

```powershell
.\.venv\Scripts\python.exe assistant_runtime\main.py --stop
```

Validacoes principais:

```powershell
npm run lint
npm run build
npm run test:runtime
npm audit --omit=dev
```

## Compatibilidade e privacidade

O modo em segundo plano foi preparado para Windows 10 ou 11, Python 3.11 ou
superior e Node.js 22 ou superior. A interface usa Chrome ou Edge quando um
deles esta instalado. Reconhecimento, respostas e sintese acontecem localmente;
internet e necessaria na primeira instalacao e quando um comando abre ou
pesquisa conteudo da web.
