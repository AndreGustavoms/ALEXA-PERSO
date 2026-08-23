import unittest

from assistant_runtime.assistant_commands.models import WindowContext
from assistant_runtime.assistant_commands.parser import IntentParser


class IntentParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = IntentParser()
        self.browser = WindowContext(handle=1, process_name="chrome.exe", kind="browser")
        self.application = WindowContext(handle=2, process_name="code.exe", kind="application")

    def assert_intent(self, phrase: str, intent_id: str, *, browser: bool = True) -> None:
        context = self.browser if browser else self.application
        parsed = self.parser.parse(phrase, context)
        self.assertIsNotNone(parsed, phrase)
        self.assertEqual(parsed.spec.id, intent_id, phrase)  # type: ignore[union-attr]

    def test_required_phrase_matrix(self) -> None:
        cases = {
            "fecha essa página": "browser.close_tab",
            "fecha essa aba": "browser.close_tab",
            "fecha o chrome": "application.close",
            "abre chrome": "application.open",
            "abre o youtube": "browser.open_site",
            "entra no github": "browser.open_site",
            "pesquisa melhores notebooks": "browser.search",
            "nova aba": "browser.new_tab",
            "reabre a aba": "browser.reopen_tab",
            "atualiza": "browser.refresh",
            "volta": "browser.back",
            "vai pra frente": "browser.forward",
            "minimiza": "window.minimize",
            "maximiza": "window.maximize",
            "mostra a área de trabalho": "window.desktop",
            "aumenta o volume": "audio.volume_up",
            "volume 50": "audio.set_volume",
            "muta": "audio.mute",
            "pausa": "media.play_pause",
            "próxima música": "media.next",
            "abre downloads": "files.open_folder",
            "abre configurações": "settings.open_configuracoes",
            "abre bluetooth": "settings.open_bluetooth",
            "abre o bluetooth": "settings.open_bluetooth",
            "tira um print": "screen.screenshot",
            "bloqueia o computador": "system.lock",
            "desliga o computador": "system.shutdown",
            "reinicia o computador": "system.restart",
            "aumenta 10": "audio.volume_up",
            "coloca em 30%": "audio.set_volume",
            "play": "media.play_pause",
            "música anterior": "media.previous",
            "página inicial": "browser.home",
            "coloca essa janela do lado esquerdo": "window.snap_left",
            "coloca do lado direito": "window.snap_right",
            "fecha o programa atual": "application.close",
        }
        for phrase, intent_id in cases.items():
            with self.subTest(phrase=phrase):
                self.assert_intent(phrase, intent_id)

    def test_parameter_extraction(self) -> None:
        volume = self.parser.parse("coloca o volume em 35%", self.browser)
        search = self.parser.parse("procura previsão do tempo", self.browser)
        url = self.parser.parse("abre github.com", self.browser)
        typed = self.parser.parse("escreve meu nome aqui", self.browser)

        self.assertEqual(volume.parameters["value"], 35)  # type: ignore[union-attr]
        self.assertEqual(search.parameters["query"], "previsao do tempo")  # type: ignore[union-attr]
        self.assertEqual(url.parameters["target"], "https://github.com")  # type: ignore[union-attr]
        self.assertEqual(typed.spec.id, "keyboard.type_text")  # type: ignore[union-attr]
        self.assertEqual(typed.parameters["text"], "meu nome aqui")  # type: ignore[union-attr]

    def test_accepts_doktor_wake_prefixes(self) -> None:
        self.assert_intent("Olá, Doktor, abra o YouTube", "browser.open_site")
        self.assert_intent("Olá, doutor, abra o YouTube", "browser.open_site")

    def test_context_changes_what_close_this_means(self) -> None:
        browser = self.parser.parse("fecha aqui", self.browser)
        application = self.parser.parse("fecha aqui", self.application)

        self.assertEqual(browser.spec.id, "browser.close_tab")  # type: ignore[union-attr]
        self.assertEqual(application.spec.id, "window.close")  # type: ignore[union-attr]

    def test_spotify_defaults_to_installed_application(self) -> None:
        application = self.parser.parse("abre o Spotify", self.application)
        website = self.parser.parse("abre o site do Spotify", self.application)

        self.assertEqual(application.spec.id, "application.open")  # type: ignore[union-attr]
        self.assertEqual(website.spec.id, "browser.open_site")  # type: ignore[union-attr]

    def test_recovers_bare_web_destination_from_speech(self) -> None:
        for phrase in ("o youtube para mim", "youtube", "o whatsapp"):
            intent = self.parser.parse(phrase, self.application)
            self.assertIsNotNone(intent)
            self.assertEqual(intent.spec.id, "browser.open_site")  # type: ignore[union-attr]

    def test_bare_close_is_ambiguous(self) -> None:
        parsed = self.parser.parse("fecha", self.browser)

        self.assertEqual(parsed.spec.id, "assistant.ambiguous_close")  # type: ignore[union-attr]

    def test_close_named_web_target_closes_current_browser_tab(self) -> None:
        parsed = self.parser.parse("fecha o YouTube", self.browser)
        self.assertEqual(parsed.spec.id, "browser.close_tab")  # type: ignore[union-attr]

    def test_prompt_voice_phrase_matrix(self) -> None:
        cases = {
            "abre o Chrome": "application.open",
            "fecha o YouTube": "browser.close_tab",
            "abre meu projeto": "files.open_folder",
            "abaixa o volume para cinquenta por cento": "audio.set_volume",
            "abre o GitHub do DoktorDev": "browser.open_github_profile",
        }
        for phrase, intent_id in cases.items():
            with self.subTest(phrase=phrase):
                self.assert_intent(phrase, intent_id)

        volume = self.parser.parse(
            "abaixa o volume para cinquenta por cento", self.browser
        )
        self.assertEqual(volume.parameters["value"], 50)  # type: ignore[union-attr]

    def test_recovers_valorant_from_common_vosk_transcription(self) -> None:
        for phrase in ("abre o valor antes", "abrir valor ante", "inicia valora antes"):
            with self.subTest(phrase=phrase):
                intent = self.parser.parse(phrase, self.application)
                self.assertIsNotNone(intent)
                self.assertEqual(intent.spec.id, "application.open")  # type: ignore[union-attr]
                self.assertEqual(intent.parameters["application"], "valorant")  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
