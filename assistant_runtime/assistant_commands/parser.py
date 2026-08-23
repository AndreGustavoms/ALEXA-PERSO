from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from .models import CommandSpec, ParsedIntent, WindowContext
from .normalization import extract_percent, normalize_text
from .registry import COMMANDS, command

WEBSITES = {
    "youtube": ("YouTube", "https://www.youtube.com"),
    "github": ("GitHub", "https://github.com"),
    "google": ("Google", "https://www.google.com"),
    "gmail": ("Gmail", "https://mail.google.com"),
    "whatsapp": ("WhatsApp", "https://web.whatsapp.com"),
    "zap": ("WhatsApp", "https://web.whatsapp.com"),
    "instagram": ("Instagram", "https://www.instagram.com"),
    "netflix": ("Netflix", "https://www.netflix.com"),
    "spotify": ("Spotify", "https://open.spotify.com"),
    "facebook": ("Facebook", "https://www.facebook.com"),
}

FOLDERS = {
    "downloads": ("Downloads", "shell:Downloads"),
    "meus downloads": ("Downloads", "shell:Downloads"),
    "documentos": ("Documentos", "shell:Personal"),
    "meus documentos": ("Documentos", "shell:Personal"),
    "imagens": ("Imagens", "shell:My Pictures"),
    "fotos": ("Imagens", "shell:My Pictures"),
    "videos": ("Videos", "shell:My Video"),
    "musicas": ("Musicas", "shell:My Music"),
    "musica": ("Musicas", "shell:My Music"),
    "desktop": ("Area de Trabalho", "shell:Desktop"),
    "area de trabalho": ("Area de Trabalho", "shell:Desktop"),
    "capturas de tela": ("Capturas de Tela", "shell:Screenshots"),
    "screenshots": ("Capturas de Tela", "shell:Screenshots"),
    "meu projeto": ("Projeto Doktor", str(Path(__file__).resolve().parents[2])),
}

SETTINGS = {
    "configuracoes": ("Configuracoes", "ms-settings:"),
    "wifi": ("Wi-Fi", "ms-settings:network-wifi"),
    "wi-fi": ("Wi-Fi", "ms-settings:network-wifi"),
    "bluetooth": ("Bluetooth", "ms-settings:bluetooth"),
    "som": ("Som", "ms-settings:sound"),
    "tela": ("Tela", "ms-settings:display"),
    "armazenamento": ("Armazenamento", "ms-settings:storagesense"),
    "aplicativos": ("Aplicativos", "ms-settings:appsfeatures"),
    "windows update": ("Windows Update", "ms-settings:windowsupdate"),
    "rede": ("Rede", "ms-settings:network-status"),
    "dispositivos": ("Dispositivos", "ms-settings:devices"),
}

OPEN_WORDS = r"(?:abre|abra|abrir|inicia|inicie|iniciar|entra|entre|entrar|acessa|acesse|acessar)"
CLOSE_WORDS = r"(?:fecha|feche|fechar|encerra|encerre|encerrar)"
SEARCH_WORDS = r"(?:pesquisa|pesquise|pesquisar|procura|procure|procurar|busca|busque|buscar)"

APPLICATION_SPEECH_ALIASES = {
    "valor antes": "valorant",
    "valor ante": "valorant",
    "valora antes": "valorant",
}


def normalize_application_name(value: str) -> str:
    name = value.strip()
    return APPLICATION_SPEECH_ALIASES.get(name, name)


class IntentParser:
    def __init__(self, commands: tuple[CommandSpec, ...] = COMMANDS) -> None:
        self.commands = commands
        self._compiled = tuple(
            (spec, tuple(re.compile(rf"^(?:{alias})$") for alias in spec.aliases))
            for spec in commands
        )

    def parse(self, transcript: str, context: WindowContext | None = None) -> ParsedIntent | None:
        text = normalize_text(transcript)
        if not text:
            return None

        for spec, patterns in self._compiled:
            if any(pattern.fullmatch(text) for pattern in patterns):
                if not self._context_matches(spec, context):
                    continue
                return ParsedIntent(spec, dict(spec.executor_params), 0.96, text)

        parameterized = self._parse_parameterized(text, context)
        if parameterized:
            return ParsedIntent(
                parameterized.spec,
                parameterized.parameters,
                parameterized.confidence,
                text,
            )

        if re.fullmatch(r"(?:fecha|feche|fechar|encerra|encerrar)", text):
            spec = command(
                "assistant.ambiguous_close",
                "Escolher o que fechar",
                "Assistente",
                (),
                "clarify",
                success="Quer fechar a aba ou a janela?",
            )
            return ParsedIntent(spec, {}, 1.0, text)
        if (
            re.fullmatch(r"(?:fecha|feche|fechar|pode fechar) (?:isso|aqui)", text)
            and context
            and context.available
            and context.kind != "browser"
        ):
            return self._dynamic(
                "window.close",
                "Fechar janela atual",
                "Janelas",
                "window",
                {"operation": "close"},
                "Fechei a janela.",
                risk="contextual",
            )
        return None

    @staticmethod
    def _context_matches(spec: CommandSpec, context: WindowContext | None) -> bool:
        required = spec.executor_params.get("context")
        if not required:
            return True
        if not context or not context.available:
            return False
        return context.kind == required

    def _parse_parameterized(
        self,
        text: str,
        context: WindowContext | None,
    ) -> ParsedIntent | None:
        type_text = re.fullmatch(
            r"(?:escreve|escreva|escrever|digita|digite|digitar)"
            r"(?: pra mim| para mim)?(?: aqui)?(?: o texto)? (.+)",
            text,
        )
        if type_text:
            value = type_text.group(1).strip()
            return self._dynamic(
                "keyboard.type_text",
                "Digitar texto",
                "Teclado",
                "type_text",
                {"text": value},
                "Digitei o texto.",
                risk="contextual",
            )

        volume = re.fullmatch(
            r"(?:(?:coloca|deixa|abaixa|reduz)(?: o volume)? (?:em|para) |"
            r"(?:o )?volume(?: em| no| para)? )(.+)",
            text,
        )
        if volume:
            value = extract_percent(volume.group(1))
            if value is None:
                return None
            if value > 100:
                return self._dynamic("audio.invalid_volume", "Validar volume", "Audio", "clarify", {}, "O volume precisa estar entre 0 e 100.")
            return self._dynamic("audio.set_volume", "Definir volume", "Audio", "set_volume", {"value": value}, "Volume em {value}%.")

        brightness = re.fullmatch(r"(?:coloca |deixa )?(?:o )?brilho(?: em| no)? (\d{1,3})(?: por cento)?", text)
        if brightness:
            value = int(brightness.group(1))
            if value > 100:
                return self._dynamic("screen.invalid_brightness", "Validar brilho", "Tela", "clarify", {}, "O brilho precisa estar entre 0 e 100.")
            return self._dynamic("screen.set_brightness", "Definir brilho", "Tela", "set_brightness", {"value": value}, "Brilho em {value}%.")

        relative_brightness = re.fullmatch(r"(aumenta|sobe|abaixa|diminui|reduz) (?:o )?brilho(?: em (\d{1,2}))?", text)
        if relative_brightness:
            direction = 1 if relative_brightness.group(1) in {"aumenta", "sobe"} else -1
            amount = int(relative_brightness.group(2) or 10)
            return self._dynamic("screen.brightness_up" if direction > 0 else "screen.brightness_down", "Alterar brilho", "Tela", "change_brightness", {"amount": direction * min(amount, 100)}, "Brilho ajustado.")

        relative_volume = re.fullmatch(r"(aumenta|sobe|abaixa|diminui|reduz) (\d{1,2})", text)
        if relative_volume:
            direction = 1 if relative_volume.group(1) in {"aumenta", "sobe"} else -1
            return self._dynamic(
                "audio.volume_up" if direction > 0 else "audio.volume_down",
                "Alterar volume",
                "Audio",
                "volume_relative",
                {"direction": direction, "amount": int(relative_volume.group(2))},
                "Ajustei o volume.",
            )

        search = re.fullmatch(rf"{SEARCH_WORDS}(?: por)? (.+)", text)
        if search:
            query = search.group(1).strip()
            windows_match = re.fullmatch(r"(?:arquivo )?(.+?) (?:no computador|no windows)", query)
            if windows_match:
                return self._dynamic("windows.search", "Pesquisar no Windows", "Sistema", "windows_search", {"query": windows_match.group(1)}, "Abri a pesquisa do Windows.")
            local_terms = set(SETTINGS) | set(FOLDERS) | {
                "calculadora", "chrome", "discord", "edge", "firefox",
                "spotify", "steam", "terminal", "vs code",
            }
            if query.startswith("arquivo ") or query in local_terms:
                return self._dynamic("windows.search", "Pesquisar no Windows", "Sistema", "windows_search", {"query": query.removeprefix("arquivo ")}, "Abri a pesquisa do Windows.")
            destination = "google"
            target = re.search(r" (?:no|na) (youtube|google)$", query)
            if target:
                destination = target.group(1)
                query = query[: target.start()].strip()
            return self._dynamic("browser.search", "Pesquisar na web", "Navegador", "web_search", {"query": query, "destination": destination}, "Pesquisando {query}.")

        if re.fullmatch(r"abre (?:a )?pesquisa do windows", text):
            return self._dynamic("windows.search", "Abrir pesquisa do Windows", "Sistema", "windows_search", {"query": ""}, "Abri a pesquisa do Windows.")

        date_or_time = self._parse_information(text)
        if date_or_time:
            return date_or_time

        settings = re.fullmatch(rf"{OPEN_WORDS} (?:as |a |o )?(?:configuracoes (?:de|do|da) )?(.+)", text)
        if settings:
            target = settings.group(1).strip()
            if target in SETTINGS:
                label, uri = SETTINGS[target]
                return self._dynamic(f"settings.open_{target.replace('-', '_').replace(' ', '_')}", f"Abrir {label}", "Configuracoes", "open_resource", {"target": uri}, f"Abri {label}.")

        folder = re.fullmatch(rf"{OPEN_WORDS} (?:a |as |os |meus |minhas )?(?:pasta )?(.+)", text)
        if folder and folder.group(1).strip() in FOLDERS:
            label, target = FOLDERS[folder.group(1).strip()]
            return self._dynamic("files.open_folder", f"Abrir {label}", "Arquivos", "open_folder", {"target": target}, f"Abri {label}.")

        named_folder = re.fullmatch(rf"{OPEN_WORDS} (?:a )?pasta (.+)", text)
        if named_folder:
            name = named_folder.group(1).strip()
            return self._dynamic(
                "files.open_named_folder",
                f"Abrir pasta {name}",
                "Arquivos",
                "open_named_folder",
                {"name": name},
                f"Abri a pasta {name}.",
            )

        url = re.fullmatch(rf"{OPEN_WORDS} (?:o site )?((?:https?://)?[a-z0-9][a-z0-9.-]+\.[a-z]{{2,}}(?:/\S*)?)", text)
        if url:
            target = url.group(1)
            parsed = urlparse(target if "://" in target else f"https://{target}")
            if parsed.scheme in {"http", "https"} and parsed.hostname:
                return self._dynamic("browser.open_url", "Abrir endereco", "Navegador", "open_resource", {"target": parsed.geturl()}, "Abri o endereco.")

        site = re.fullmatch(
            rf"{OPEN_WORDS} (?:o |a |no |na )?(?:(?:site|versao web) (?:do |da )?)?(.+)",
            text,
        )
        if site and site.group(1).strip() in WEBSITES:
            site_name = site.group(1).strip()
            if site_name != "spotify" or re.search(r"\b(?:site|web)\b", text):
                label, target = WEBSITES[site_name]
                return self._dynamic("browser.open_site", f"Abrir {label}", "Navegador", "open_resource", {"target": target}, f"Abri o {label}.")

        github_profile = re.fullmatch(
            rf"{OPEN_WORDS} (?:o )?github (?:do|da|de) (.+)", text
        )
        if github_profile:
            account = re.sub(r"[^a-z0-9-]", "", github_profile.group(1))
            if account:
                return self._dynamic(
                    "browser.open_github_profile",
                    f"Abrir GitHub de {account}",
                    "Navegador",
                    "open_resource",
                    {"target": f"https://github.com/{account}"},
                    f"Abri o GitHub de {account}.",
                )

        # Speech recognition can omit the verb (for example: "o youtube").
        # Keep the well-known web destinations usable without opening arbitrary text.
        bare_site = re.fullmatch(r"(?:o |a |no |na )?(.+)", text)
        if bare_site and bare_site.group(1).strip() in WEBSITES:
            site_name = bare_site.group(1).strip()
            if site_name != "spotify":
                label, target = WEBSITES[site_name]
                return self._dynamic("browser.open_site", f"Abrir {label}", "Navegador", "open_resource", {"target": target}, f"Abri o {label}.")

        close_app = re.fullmatch(rf"{CLOSE_WORDS} (?:o |a )?(.+)", text)
        if (
            close_app
            and close_app.group(1).strip() in WEBSITES
            and context
            and context.kind == "browser"
        ):
            target = close_app.group(1).strip()
            label = WEBSITES[target][0]
            return self._dynamic(
                "browser.close_tab",
                f"Fechar {label}",
                "Navegador",
                "shortcut",
                {"keys": ("CTRL", "W"), "context": "browser"},
                f"Fechei o {label}.",
                risk="contextual",
            )
        contextual_targets = {
            "isso", "aqui", "essa pagina", "esta pagina", "pagina atual",
            "essa aba", "esta aba", "aba atual", "essa janela", "esta janela",
            "janela atual", "programa atual", "aplicativo atual",
        }
        if close_app and close_app.group(1) not in contextual_targets:
            app = normalize_application_name(close_app.group(1))
            if app in {"navegador", "browser"} and context and context.kind == "browser":
                app = context.application or context.process_name.removesuffix(".exe")
            return self._dynamic("application.close", f"Fechar {app}", "Aplicativos", "close_application", {"application": app}, f"Fechei {app}.", risk="confirmation_required", confirmation=f"Quer mesmo fechar {app}? Isso pode descartar trabalho nao salvo.")

        current_app = re.fullmatch(
            rf"{CLOSE_WORDS} (?:o )?(?:programa|aplicativo) atual",
            text,
        )
        if current_app and context and context.available:
            app = context.application or context.process_name.removesuffix(".exe")
            return self._dynamic(
                "application.close",
                f"Fechar {app}",
                "Aplicativos",
                "close_application",
                {"application": app},
                f"Fechei {app}.",
                risk="confirmation_required",
                confirmation=f"Quer mesmo fechar {app}? Isso pode descartar trabalho nao salvo.",
            )

        if re.fullmatch(rf"{OPEN_WORDS} (?:o )?navegador", text):
            return self._dynamic("browser.open", "Abrir navegador", "Navegador", "open_resource", {"target": "https://www.google.com"}, "Abri o navegador.")

        open_app = re.fullmatch(rf"{OPEN_WORDS} (?:o |a |os |as |um |uma |no |na )?(?:aplicativo |programa )?(.+)", text)
        if open_app:
            app = normalize_application_name(open_app.group(1))
            return self._dynamic("application.open", f"Abrir {app}", "Aplicativos", "open_application", {"application": app}, f"Abri {app}.")
        return None

    def _parse_information(self, text: str) -> ParsedIntent | None:
        if re.fullmatch(r"(?:que horas sao|qual (?:e )?a hora|horario)", text):
            return self._dynamic("information.time", "Informar horario", "Informacao", "tell_time", {}, "")
        if re.fullmatch(r"(?:que dia e hoje|qual (?:e )?a data|qual a data de hoje|data de hoje)", text):
            return self._dynamic("information.date", "Informar data", "Informacao", "tell_date", {}, "")
        if re.fullmatch(r"(?:que dia da semana e hoje|qual (?:e )?o dia da semana)", text):
            return self._dynamic("information.weekday", "Informar dia da semana", "Informacao", "tell_weekday", {}, "")
        return None

    @staticmethod
    def _dynamic(
        command_id: str,
        name: str,
        category: str,
        executor: str,
        parameters: dict[str, object],
        success: str,
        *,
        risk: str = "safe",
        confirmation: str = "",
    ) -> ParsedIntent:
        from .models import RiskLevel

        spec = command(
            command_id,
            name,
            category,
            (),
            executor,
            risk=RiskLevel(risk),
            success=success,
            confirmation=confirmation,
        )
        return ParsedIntent(spec, parameters, 0.98, "")
