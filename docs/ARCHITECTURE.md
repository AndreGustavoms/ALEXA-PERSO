# Arquitetura

O Doktor mantém a arquitetura existente: React/Vite gera arquivos estáticos e
um único processo Python serve interface/API, tray, voz e comandos. Node nao
faz parte do aplicativo instalado.

```text
Microfone -> wake Vosk local -> VAD -> STT provider
          -> IntentParser -> CommandRouter -> PlatformAdapter -> acao registrada
          -> TTS -> wake
```

`assistant_runtime/app_paths.py` separa recursos imutáveis do pacote dos dados
do usuário. Configurações, permissões, métricas e logs nunca são escritos na
pasta de instalação.

`VERSION` é a fonte de versão. `packaging/doktor.spec` inclui frontend, assets,
modelo e dependências nativas. O app opera com privilégio do usuário atual.

O texto transcrito nunca é entregue a shell. O registro declarativo define
intenções, parâmetros, risco, confirmação e executor permitido.

## Comandos naturais e contexto

Antes do parser, `normalize_natural_command` remove molduras de conversa como
`pode`, `consegue`, `pra mim` e `rapidinho`, preservando verbo e alvo. Sinônimos
seguros convergem para formas canônicas; por exemplo, `encerra`, `finaliza` e
`sai do` convergem para `fecha`. A mesma etapa atende abrir, janelas, mídia,
volume e pesquisa.

O parser resolve primeiro comandos deterministas registrados. Nomes conhecidos
de sites e aplicativos aceitam correspondência aproximada somente acima de
0.82 e rejeitam resultados ambíguos. Texto desconhecido continua sem executor
e nunca vira comando de shell.

Para pedidos contextuais de fechamento, a ordem é:

1. aba ativa quando o foco está em um navegador;
2. janela ou aplicativo em primeiro plano quando declarado pelo usuário;
3. último aplicativo identificado no histórico da conversa;
4. pergunta de esclarecimento quando não existe contexto suficiente.

Fechar aba, janela ou aplicativo é uma ação contextual imediata. Confirmação é
reservada para ações destrutivas, como desligar ou reiniciar o computador. Uma
nova frase executável substitui uma confirmação pendente; apenas respostas
isoladas como `sim` e `não` resolvem essa confirmação.
