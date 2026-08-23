from __future__ import annotations

from .models import CommandSpec, RiskLevel


def command(
    command_id: str,
    name: str,
    category: str,
    aliases: tuple[str, ...],
    executor: str,
    *,
    risk: RiskLevel = RiskLevel.SAFE,
    success: str = "Feito.",
    error: str = "Nao consegui fazer isso.",
    confirmation: str = "",
    **executor_params: object,
) -> CommandSpec:
    return CommandSpec(
        id=command_id,
        name=name,
        category=category,
        description=name.lower(),
        aliases=aliases,
        executor=executor,
        risk=risk,
        confirmation_prompt=confirmation,
        success_message=success,
        error_message=error,
        executor_params=dict(executor_params),
    )


COMMANDS: tuple[CommandSpec, ...] = (
    command("browser.close_tab", "Fechar aba atual", "Navegador", (r"(?:fecha|feche|fechar|encerra) (?:essa |esta |a )?(?:aba|pagina)(?: atual)?", r"pode fechar (?:isso|aqui)", r"fecha (?:isso|aqui)"), "shortcut", risk=RiskLevel.CONTEXTUAL, success="Fechei a aba.", error="Nao consegui fechar essa aba.", keys=("CTRL", "W"), context="browser"),
    command("browser.new_tab", "Abrir nova aba", "Navegador", (r"(?:abre |abrir )?(?:uma )?(?:nova|outra) aba", r"nova aba"), "shortcut", success="Abri uma nova aba.", keys=("CTRL", "T"), context="browser"),
    command("browser.reopen_tab", "Reabrir ultima aba", "Navegador", (r"reabr[aeir]* (?:a )?(?:ultima )?aba(?: que (?:eu )?fechei)?",), "shortcut", success="Reabri a ultima aba.", keys=("CTRL", "SHIFT", "T"), context="browser"),
    command("browser.next_tab", "Proxima aba", "Navegador", (r"(?:vai? |ir )?(?:para |pra )?(?:a )?proxima aba",), "shortcut", success="Fui para a proxima aba.", keys=("CTRL", "TAB"), context="browser"),
    command("browser.previous_tab", "Aba anterior", "Navegador", (r"(?:vai? |volta |ir )?(?:para |pra )?(?:a )?aba anterior",), "shortcut", success="Voltei para a aba anterior.", keys=("CTRL", "SHIFT", "TAB"), context="browser"),
    command("browser.refresh", "Atualizar pagina", "Navegador", (r"(?:atualiza|atualize|recarrega|recarregue)(?: (?:a )?(?:pagina|isso|aqui))?",), "shortcut", success="Atualizei a pagina.", keys=("CTRL", "R"), context="browser"),
    command("browser.stop", "Parar carregamento", "Navegador", (r"para(?:r)? (?:o )?carregamento",), "shortcut", success="Parei o carregamento.", keys=("ESC",), context="browser"),
    command("browser.back", "Voltar pagina", "Navegador", (r"(?:volta|volte)(?: (?:uma )?pagina)?", r"pagina anterior"), "shortcut", success="Voltei.", keys=("ALT", "LEFT"), context="browser"),
    command("browser.forward", "Avancar pagina", "Navegador", (r"(?:vai|va) (?:para |pra )?frente", r"avanca(?:r)? (?:uma )?pagina"), "shortcut", success="Avancei.", keys=("ALT", "RIGHT"), context="browser"),
    command("browser.home", "Pagina inicial", "Navegador", (r"(?:vai|va|ir|volta) (?:para |pra )?(?:a )?pagina inicial", r"pagina inicial"), "shortcut", success="Abri a pagina inicial.", keys=("ALT", "HOME"), context="browser"),
    command("browser.duplicate_tab", "Duplicar aba", "Navegador", (r"duplica(?:r)? (?:essa |esta |a )?aba",), "browser_duplicate", success="Dupliquei a aba.", context="browser"),
    command("browser.new_window", "Abrir nova janela", "Navegador", (r"abre (?:uma )?nova janela(?: do navegador)?",), "shortcut", success="Abri uma nova janela.", keys=("CTRL", "N"), context="browser"),
    command("browser.private_window", "Abrir janela privada", "Navegador", (r"abre (?:uma )?(?:janela )?(?:anonima|privada|incognito)",), "browser_private", success="Abri uma janela privada."),
    command("browser.address_bar", "Focar barra de endereco", "Navegador", (r"(?:foca|vai para|abre) (?:a )?barra de endereco",), "shortcut", success="Barra de endereco selecionada.", keys=("CTRL", "L"), context="browser"),
    command("browser.zoom_in", "Aumentar zoom", "Navegador", (r"(?:aumenta|amplia|mais) (?:o )?zoom",), "shortcut", success="Aumentei o zoom.", keys=("CTRL", "+"), context="browser"),
    command("browser.zoom_out", "Diminuir zoom", "Navegador", (r"(?:diminui|reduz|menos) (?:o )?zoom",), "shortcut", success="Diminuí o zoom.", keys=("CTRL", "-"), context="browser"),
    command("browser.zoom_reset", "Restaurar zoom", "Navegador", (r"(?:restaura|redefine|volta) (?:o )?zoom",), "shortcut", success="Restaurei o zoom.", keys=("CTRL", "0"), context="browser"),
    command("browser.fullscreen", "Alternar tela cheia", "Navegador", (r"(?:coloca|entra|abre) (?:em )?tela cheia", r"sai(?:r)? (?:da )?tela cheia"), "shortcut", success="Alternei a tela cheia.", keys=("F11",), context="browser"),
    command("browser.downloads", "Abrir downloads do navegador", "Navegador", (r"abre (?:os )?downloads do navegador",), "shortcut", success="Abri os downloads.", keys=("CTRL", "J"), context="browser"),
    command("browser.history", "Abrir historico", "Navegador", (r"abre (?:o )?historico",), "shortcut", success="Abri o historico.", keys=("CTRL", "H"), context="browser"),
    command("browser.bookmarks", "Abrir favoritos", "Navegador", (r"abre (?:os )?favoritos",), "shortcut", success="Abri os favoritos.", keys=("CTRL", "SHIFT", "O"), context="browser"),
    command("browser.close_other_tabs", "Fechar outras abas", "Navegador", (r"fecha(?:r)? (?:as )?outras abas",), "unsupported", risk=RiskLevel.BLOCKED, success="", error="Esse navegador nao oferece um atalho seguro para fechar as outras abas.", context="browser"),
    command("browser.close_tabs_right", "Fechar abas a direita", "Navegador", (r"fecha(?:r)? (?:as )?abas (?:a|para a|da) direita",), "unsupported", risk=RiskLevel.BLOCKED, success="", error="Esse navegador nao oferece um atalho seguro para fechar as abas a direita.", context="browser"),

    command("window.close", "Fechar janela atual", "Janelas", (r"(?:fecha|feche|fechar) (?:essa |esta |a )?janela(?: atual)?",), "window", risk=RiskLevel.CONTEXTUAL, success="Fechei a janela.", operation="close"),
    command("window.minimize", "Minimizar janela", "Janelas", (r"minimiza(?:r)?(?: (?:essa janela|isso|aqui|(?:o )?(?:programa|aplicativo|janela) atual))?",), "window", risk=RiskLevel.CONTEXTUAL, success="Janela minimizada.", operation="minimize"),
    command("window.maximize", "Maximizar janela", "Janelas", (r"maximiza(?:r)?(?: (?:essa janela|isso|aqui|(?:o )?(?:programa|aplicativo|janela) atual))?",), "window", risk=RiskLevel.CONTEXTUAL, success="Janela maximizada.", operation="maximize"),
    command("window.restore", "Restaurar janela", "Janelas", (r"restaura(?:r)? (?:essa |esta |a )?janela", r"restaura(?:r)? (?:o )?(?:programa|aplicativo) atual"), "window", risk=RiskLevel.CONTEXTUAL, success="Janela restaurada.", operation="restore"),
    command("window.switch", "Alternar janela", "Janelas", (r"(?:vai|va|muda|troca) (?:para |pra )?(?:a )?(?:outra|proxima) janela", r"alterna(?:r)? (?:a )?janela"), "shortcut", success="Troquei de janela.", keys=("ALT", "TAB")),
    command("window.previous", "Voltar para janela anterior", "Janelas", (r"volta (?:para |pra )?(?:a )?janela anterior",), "shortcut", success="Voltei para a janela anterior.", keys=("ALT", "SHIFT", "TAB")),
    command("window.desktop", "Mostrar area de trabalho", "Janelas", (r"mostra(?:r)? (?:a )?(?:area de trabalho|desktop)",), "shortcut", success="Mostrei a area de trabalho.", keys=("WIN", "D")),
    command("window.snap_left", "Mover janela para esquerda", "Janelas", (r"(?:coloca|move|joga) (?:essa janela |isso )?(?:do lado |para |pra )?(?:a )?esquerd[ao]",), "shortcut", risk=RiskLevel.CONTEXTUAL, success="Coloquei a janela a esquerda.", keys=("WIN", "LEFT")),
    command("window.snap_right", "Mover janela para direita", "Janelas", (r"(?:coloca|move|joga) (?:essa janela |isso )?(?:do lado |para |pra )?(?:a )?direit[ao]",), "shortcut", risk=RiskLevel.CONTEXTUAL, success="Coloquei a janela a direita.", keys=("WIN", "RIGHT")),
    command("window.task_view", "Abrir visao de tarefas", "Janelas", (r"abre (?:a )?visao de tarefas",), "shortcut", success="Abri a visao de tarefas.", keys=("WIN", "TAB")),
    command("window.fullscreen", "Colocar janela em tela cheia", "Janelas", (r"coloca (?:essa |esta |a )?janela (?:em )?tela cheia",), "window", risk=RiskLevel.CONTEXTUAL, success="Janela em tela cheia.", operation="maximize"),

    command("audio.volume_up", "Aumentar volume", "Audio", (r"(?:aumenta|aumente|sobe|suba|eleva) (?:o )?volume(?: em \d+)?",), "volume_relative", success="Aumentei o volume.", direction=1),
    command("audio.volume_down", "Diminuir volume", "Audio", (r"(?:abaixa|abaixe|diminui|diminua|reduz) (?:o )?volume(?: em \d+)?",), "volume_relative", success="Diminuí o volume.", direction=-1),
    command("audio.mute", "Silenciar audio", "Audio", (r"(?:muta|mute|silencia|silencie)(?: (?:o )?(?:som|audio|computador))?",), "set_mute", success="Som silenciado.", muted=True),
    command("audio.unmute", "Ativar audio", "Audio", (r"(?:desmuta|tira|sai) (?:o som )?(?:do )?mudo",), "set_mute", success="Som ativado.", muted=False),
    command("media.play_pause", "Alternar reproducao", "Midia", (r"(?:play|pausa|pause|continua|continue|toca|tocar|pode tocar|reproduz|reproduza)(?: (?:a )?(?:musica|midia|video))?",), "media_key", success="Feito.", code=14),
    command("media.next", "Proxima faixa", "Midia", (r"(?:proxima|proximo|avanca|avance)(?: (?:a )?(?:musica|faixa))?",), "media_key", success="Proxima faixa.", code=11),
    command("media.previous", "Faixa anterior", "Midia", (r"(?:volta|anterior)(?: (?:a )?(?:musica|faixa))", r"(?:musica|faixa) anterior"), "media_key", success="Faixa anterior.", code=12),
    command("media.stop", "Parar midia", "Midia", (r"para(?:r)? (?:a )?(?:musica|midia|reproducao)",), "media_key", success="Parei a reproducao.", code=13),

    command("system.lock", "Bloquear computador", "Sistema", (r"bloqueia(?:r)? (?:o )?(?:computador|pc|windows)",), "system", success="Computador bloqueado.", operation="lock"),
    command("system.shutdown", "Desligar computador", "Sistema", (r"(?:desliga|desligue|desligar) (?:o )?(?:computador|pc|windows)",), "system", risk=RiskLevel.CONFIRMATION_REQUIRED, confirmation="Quer mesmo desligar o computador?", success="Desligando o computador.", operation="shutdown"),
    command("system.restart", "Reiniciar computador", "Sistema", (r"(?:reinicia|reinicie|reiniciar) (?:o )?(?:computador|pc|windows)",), "system", risk=RiskLevel.CONFIRMATION_REQUIRED, confirmation="Quer mesmo reiniciar o computador?", success="Reiniciando o computador.", operation="restart"),
    command("system.sign_out", "Sair da conta", "Sistema", (r"(?:sai|sair|encerra) (?:da |minha )?(?:conta|sessao)",), "system", risk=RiskLevel.CONFIRMATION_REQUIRED, confirmation="Quer mesmo sair da sua conta?", success="Saindo da conta.", operation="sign_out"),
    command("system.sleep", "Suspender computador", "Sistema", (r"(?:suspende|suspender|coloca para dormir) (?:o )?(?:computador|pc)?",), "system", risk=RiskLevel.CONFIRMATION_REQUIRED, confirmation="Quer suspender o computador agora?", success="Suspendendo o computador.", operation="sleep"),
    command("system.hibernate", "Hibernar computador", "Sistema", (r"(?:hiberna|hibernar) (?:o )?(?:computador|pc)?",), "system", risk=RiskLevel.CONFIRMATION_REQUIRED, confirmation="Quer hibernar o computador agora?", success="Hibernando o computador.", operation="hibernate"),

    command("editing.copy", "Copiar", "Edicao", (r"copia(?:r)?(?: (?:isso|aqui|item selecionado))?",), "shortcut", success="Copiei.", keys=("CTRL", "C")),
    command("editing.paste", "Colar", "Edicao", (r"cola(?:r)?(?: (?:isso|aqui))?",), "shortcut", success="Colei.", keys=("CTRL", "V")),
    command("editing.cut", "Recortar", "Edicao", (r"recorta(?:r)?(?: (?:isso|aqui|item selecionado))?",), "shortcut", success="Recortei.", keys=("CTRL", "X")),
    command("editing.select_all", "Selecionar tudo", "Edicao", (r"seleciona(?:r)? tudo",), "shortcut", success="Selecionei tudo.", keys=("CTRL", "A")),
    command("editing.undo", "Desfazer", "Edicao", (r"(?:desfaz|desfazer)",), "shortcut", success="Desfiz.", keys=("CTRL", "Z")),
    command("editing.redo", "Refazer", "Edicao", (r"(?:refaz|refazer)",), "shortcut", success="Refiz.", keys=("CTRL", "Y")),
    command("editing.find", "Localizar", "Edicao", (r"abre (?:a )?(?:busca|pesquisa) (?:nesta|nessa) (?:pagina|janela)",), "shortcut", success="Abri a busca.", keys=("CTRL", "F")),
    command("keyboard.enter", "Pressionar Enter", "Teclado", (r"(?:aperta|aperte|pressiona|pressione) (?:a tecla )?enter", r"(?:da|de) enter"), "shortcut", risk=RiskLevel.CONTEXTUAL, success="Pressionei Enter.", keys=("ENTER",)),

    command("files.back", "Voltar pasta", "Arquivos", (r"volta(?:r)? (?:uma )?pasta",), "shortcut", success="Voltei uma pasta.", keys=("ALT", "LEFT"), context="explorer"),
    command("files.forward", "Avancar pasta", "Arquivos", (r"avanca(?:r)? (?:uma )?pasta",), "shortcut", success="Avancei uma pasta.", keys=("ALT", "RIGHT"), context="explorer"),
    command("files.up", "Subir um nivel", "Arquivos", (r"(?:sobe|suba|subir) (?:uma pasta|um nivel)",), "shortcut", success="Subi um nivel.", keys=("ALT", "UP"), context="explorer"),
    command("files.new_folder", "Criar nova pasta", "Arquivos", (r"cria(?:r)? (?:uma )?(?:nova )?pasta",), "shortcut", success="Criei uma nova pasta.", keys=("CTRL", "SHIFT", "N"), context="explorer"),
    command("files.rename", "Renomear item", "Arquivos", (r"renomeia(?:r)? (?:isso|item selecionado)?",), "shortcut", success="Pronto para renomear.", keys=("F2",), context="explorer"),
    command("files.delete", "Excluir item", "Arquivos", (r"(?:exclui|excluir|apaga|apagar|deleta|deletar) (?:isso|item selecionado|arquivo|pasta)",), "shortcut", risk=RiskLevel.CONFIRMATION_REQUIRED, confirmation="Quer mover o item selecionado para a Lixeira?", success="Movi o item para a Lixeira.", keys=("DELETE",), context="explorer"),

    command("screen.screenshot", "Capturar tela", "Tela", (r"(?:tira|tire|faz|faca) (?:um )?print", r"captura(?:r)? (?:a )?tela"), "shortcut", success="Capturei a tela.", keys=("WIN", "PRINTSCREEN")),
    command("screen.capture_window", "Capturar janela", "Tela", (r"captura(?:r)? (?:essa |esta |a )?janela",), "shortcut", success="Copiei a captura da janela.", keys=("ALT", "PRINTSCREEN")),
    command("screen.snipping_tool", "Abrir ferramenta de captura", "Tela", (r"abre (?:a )?ferramenta de captura",), "shortcut", success="Abri a ferramenta de captura.", keys=("WIN", "SHIFT", "S")),
)


COMMAND_BY_ID = {spec.id: spec for spec in COMMANDS}


def get_command(command_id: str) -> CommandSpec:
    return COMMAND_BY_ID[command_id]
