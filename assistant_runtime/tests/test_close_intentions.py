import unittest

from assistant_runtime.assistant_commands.models import CommandIntent, WindowContext
from assistant_runtime.assistant_commands.parser import IntentParser
from assistant_runtime.assistant_commands.router import CommandRouter


CLOSE_TEMPLATES = (
    "fecha {target}",
    "fecha o {target}",
    "pode fechar o {target}",
    "pode fechar o {target} pra mim",
    "fecha ai o {target}",
    "fecha o {target} ai pra mim",
    "encerra o {target}",
    "finaliza o {target}",
    "tira o {target}",
    "fecha esse {target}",
    "quero que feche o {target}",
    "voce consegue fechar o {target}",
    "consegue fechar o {target}",
    "Doktor fecha o {target}",
)
YOUTUBE_ALIASES = (
    "youtube",
    "you tube",
    "yutube",
    "iutube",
    "yt",
    "you tubi",
    "youtubee",
    "you tu be",
)
CLOSE_PHRASES = tuple(
    template.format(target=target)
    for template in CLOSE_TEMPLATES
    for target in YOUTUBE_ALIASES
)


class CloseApplicationIntentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = IntentParser()
        self.router = CommandRouter(self.parser)
        self.browser = WindowContext(
            handle=10,
            process_name="chrome.exe",
            title="YouTube - Google Chrome",
            application="Chrome",
            kind="browser",
        )

    def test_more_than_one_hundred_natural_close_variants(self) -> None:
        self.assertGreaterEqual(len(CLOSE_PHRASES), 100)

        for phrase in CLOSE_PHRASES:
            with self.subTest(phrase=phrase):
                intents = self.router.parse(phrase, self.browser)
                self.assertEqual(len(intents), 1)
                intent = intents[0]
                self.assertEqual(intent.kind, CommandIntent.CLOSE_APPLICATION)
                self.assertEqual(intent.spec.id, "browser.close_tab")
                self.assertEqual(intent.parameters.get("target"), "youtube")

    def test_negative_close_phrases_never_execute(self) -> None:
        phrases = (
            "eu fechei o youtube ontem",
            "sera que eu deveria fechar o youtube",
            "como fecha o youtube",
            "nao fecha o youtube",
            "não feche o youtube",
            "o youtube fechou sozinho",
            "por que fechar o youtube",
            "quando fechar o youtube",
            "eu não quero fechar o youtube",
            "voce fechou o youtube",
            "ele encerrou o youtube",
            "ela finalizou o youtube",
            "gosto de fechar ciclos no youtube",
            "tutorial de como fechar youtube",
            "deveria fechar o youtube",
        )
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertEqual(self.router.parse(phrase, self.browser), ())

    def test_semantic_fallback_returns_structure_only(self) -> None:
        intent = self.router.parse("remove o youtube da tela", self.browser)[0]

        self.assertEqual(intent.kind, CommandIntent.CLOSE_APPLICATION)
        self.assertEqual(intent.parameters["target"], "youtube")
        self.assertEqual(intent.source, "semantic-local")
        self.assertNotIn("shell", intent.parameters)

    def test_required_context_sequence_survives(self) -> None:
        contextual = self.router.parse("fecha ai pra mim", self.browser, "youtube")[0]
        explicit = self.router.parse("fecha isso", self.browser, "youtube")[0]
        tab = self.router.parse("fecha essa aba", self.browser, "youtube")[0]

        for intent in (contextual, explicit, tab):
            self.assertEqual(intent.kind, CommandIntent.CLOSE_APPLICATION)
            self.assertEqual(intent.spec.id, "browser.close_tab")

    def test_explicit_target_never_closes_an_unrelated_active_tab(self) -> None:
        context = WindowContext(
            handle=11,
            process_name="chrome.exe",
            title="GitHub - Google Chrome",
            application="Chrome",
            kind="browser",
        )
        intent = self.router.parse("fecha o youtube", context)[0]

        self.assertEqual(intent.parameters["target"], "youtube")
        self.assertNotIn("youtube", context.title.lower())


def _make_close_variant_test(phrase: str):
    def test(self: CloseApplicationIntentTests) -> None:
        intent = self.router.parse(phrase, self.browser)[0]
        self.assertEqual(intent.kind, CommandIntent.CLOSE_APPLICATION)
        self.assertEqual(intent.spec.id, "browser.close_tab")
        self.assertEqual(intent.parameters.get("target"), "youtube")

    return test


for _index, _phrase in enumerate(CLOSE_PHRASES):
    setattr(
        CloseApplicationIntentTests,
        f"test_close_youtube_variant_{_index:03d}",
        _make_close_variant_test(_phrase),
    )


if __name__ == "__main__":
    unittest.main()
