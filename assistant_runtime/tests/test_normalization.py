import unittest

from assistant_runtime.assistant_commands.normalization import normalize_natural_command


class NaturalCommandNormalizationTests(unittest.TestCase):
    def test_removes_conversational_framing_without_losing_target(self) -> None:
        cases = {
            "Pode fechar pra mim o YouTube?": "fecha o youtube",
            "Doktor, consegue fechar isso ai?": "fecha isso",
            "Eu quero que abra o Spotify rapidinho": "abre o spotify",
            "Gostaria que iniciasse o Chrome": "iniciasse o chrome",
            "Eu confirmo, pode fechar o YouTube": "fecha o youtube",
            "Tira isso daqui": "fecha isso",
            "Sai do GitHub": "fecha github",
            "Pode aumentar o volume por favor": "aumenta o volume",
            "Pode pausar ai": "pausa",
        }
        for phrase, expected in cases.items():
            with self.subTest(phrase=phrase):
                self.assertEqual(normalize_natural_command(phrase), expected)

    def test_does_not_rewrite_non_command_conversation(self) -> None:
        self.assertEqual(
            normalize_natural_command("Eu gosto de fechar ciclos"),
            "eu gosto de fechar ciclos",
        )


if __name__ == "__main__":
    unittest.main()
