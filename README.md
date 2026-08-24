<p align="center">
  <img src="public/doktor-mark.svg" width="88" alt="Doktor" />
</p>

# Doktor Assistant

Assistente local do ecossistema Doktor. Permanece em segundo plano, reconhece uma frase de
ativacao sem enviar o audio para um servidor e responde usando a voz instalada
no computador.

## Instalar (recomendado)

Abra [GitHub Releases](https://github.com/AndreGustavoms/ALEXA-PERSO/releases),
baixe o instalador do seu sistema e execute normalmente. O pacote inclui o
runtime, a interface e o modelo local; o usuário não precisa instalar Python,
Node.js ou usar terminal.

Pacotes atuais: Windows x64 e Linux x64/ARM64. macOS e Windows ARM64 estão
bloqueados pelos binários disponíveis do Vosk 0.3.45; detalhes em
`docs/BUILD.md`.

## Instalar pelo código-fonte

De dois cliques em `INSTALAR_ASSISTENTE.cmd`.

O instalador prepara o ambiente Python, baixa o modelo de portugues, instala a
interface, cria o atalho `Doktor Assistant` na area de trabalho e configura o
inicio automatico com o Windows. Depois disso, o aplicativo fica disponivel no
icone da bandeja do sistema.

Para instalar a partir do repositorio privado do GitHub, clone o projeto com
GitHub Desktop ou com uma sessao autenticada do Git e execute o instalador:

```powershell
git clone https://github.com/AndreGustavoms/ALEXA-PERSO.git
cd ALEXA-PERSO
.\INSTALAR_ASSISTENTE.cmd
```

A instalacao clonada usa `git pull` automaticamente para buscar atualizacoes.
Um ZIP de um repositorio privado precisa de um `DOKTOR_GITHUB_TOKEN` ou do
GitHub CLI autenticado para permitir atualizacoes sem Git.

## Usar

1. Diga `Ola, Doktor`.
2. Aguarde o sinal sonoro e `Sim, pode falar`.
3. Comece a falar em ate dez segundos.
4. Depois que a fala comeca, nao existe limite de duracao.
5. Com OpenAI ativa, o Semantic VAD decide quando a frase terminou. No modo
   local, cerca de um segundo de silencio continuo encerra o comando.

Somente a frase de ativacao `Ola, Doktor` abre a escuta de comandos.

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
- `Feche o YouTube e depois abra o Spotify` executa as duas intencoes em ordem.

## Transcricao de alta precisao

O Doktor funciona sem conta externa usando Vosk local. Para ativar a
transcricao OpenAI Realtime com `gpt-4o-transcribe`, Semantic VAD e reducao de
ruido, execute `CONFIGURAR_OPENAI.cmd` e informe sua `OPENAI_API_KEY`. A chave e
protegida pelo DPAPI da sua conta do Windows e nunca e enviada para a interface.

O modo `auto` usa OpenAI apenas depois da wake word. Se a chave, rede ou API
falhar, o mesmo audio ja esta sendo processado pelo Vosk e o comando continua
localmente. O audio bruto fica somente em memoria e nao e salvo em disco.

Edite `assistant_runtime/transcription_vocabulary.txt` para acrescentar nomes
de programas, projetos e termos recorrentes. O perfil de microfone e configurado
em `assistant_runtime/stt_config.json`: use `near_field` para headset e
`far_field` para microfone de notebook ou distante.

`Feche esta pagina` fecha somente a aba atual quando um navegador esta em
foco. `Feche o Chrome` e uma intencao diferente, direcionada ao aplicativo
inteiro, e exige confirmacao porque pode haver trabalho nao salvo.

Fechar a interface nao encerra o assistente. Use o icone na bandeja para abrir
a interface, pausar a escuta, ativar ou desativar o inicio com o Windows e
encerrar completamente.

O inicializador mantem somente um processo permanente do assistente. Abrir o
atalho novamente apenas mostra a interface existente. A cada 24 horas ele
verifica a branch `main` do GitHub e atualiza o aplicativo automaticamente,
preservando modelo, permissoes e configuracoes locais.

Para atualizar imediatamente, execute `ATUALIZAR_ASSISTENTE.cmd`. O instalador
continua disponivel para uma instalacao inicial feita a partir do ZIP do GitHub.

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
- `assistant_runtime/stt.py`: provedores Vosk/OpenAI, Semantic VAD e fallback.
- `assistant_runtime/stt_config.json`: modelo, idioma e perfil de ruido.
- `assistant_runtime/transcription_vocabulary.txt`: contexto extensivel do STT.
- `assistant_runtime/voice_metrics.py`: metricas agregadas, sem audio bruto.
- `assistant_runtime/assistant_commands/router.py`: comandos simples e compostos.
- `App.tsx`, `components/` e `app/globals.css`: interface responsiva em React.
- `hooks/`: integracoes isoladas com o runtime local e APIs de voz do navegador.
- `lib/`: respostas iniciais e mensagens de erro.
- `scripts/install-assistant.ps1`: instalacao, build, atalho e inicializacao.
- `runtime/`: modelo e logs gerados localmente, fora do Git.

O runtime usa um pipeline hibrido. Uma gramatica Vosk pequena fica ouvindo
localmente apenas a frase de ativacao. Depois dela, a sessao Realtime recebe
somente o comando e usa reducao de ruido, contexto em portugues e Semantic VAD.
O Vosk roda em paralelo como fallback, sem prazo maximo depois do inicio da fala.

As metricas agregadas ficam em `runtime/config/voice-metrics.json`: ativacoes,
duracao enviada, latencia, erros e fallbacks. O custo estimado permanece nulo
porque a cobranca oficial do modelo e por tokens de audio, nao por uma taxa fixa
confiavel por minuto no cliente.

Os valores ficam centralizados em `assistant_runtime/voice_config.json`:

```json
{
  "activation_start_timeout": 7.0,
  "speech_end_silence": 0.9,
  "minimum_speech_duration": 0.24,
  "maximum_phrase_duration": null,
  "vad_aggressiveness": 3
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

O pacote Windows foi validado no Windows 10 x64. Os pacotes Linux x64 e ARM64
são gerados nativamente pelo GitHub Actions. Python 3.11+ e Node.js 22+ são
necessários apenas para desenvolvimento. Reconhecimento, respostas e síntese
acontecem localmente; internet é usada por updates e por recursos web/OpenAI.

Documentação técnica: `docs/ARCHITECTURE.md`, `docs/BUILD.md`,
`docs/RELEASE.md`, `docs/PLATFORM_ADAPTERS.md`, `docs/VOICE_ENGINE.md` e
`docs/TROUBLESHOOTING.md`.
