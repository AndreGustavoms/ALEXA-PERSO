import unittest

from assistant_runtime.replies import create_assistant_reply


class CreateAssistantReplyTests(unittest.TestCase):
    def test_greets_without_requiring_accents(self) -> None:
        reply = create_assistant_reply("ola, tudo bem?")

        self.assertIn("Como posso ajudar", reply)

    def test_explains_initial_capability(self) -> None:
        reply = create_assistant_reply("como funciona?")

        self.assertIn("abrir sites", reply)

    def test_echoes_an_unknown_command(self) -> None:
        reply = create_assistant_reply("  abra   a agenda  ")

        self.assertIn("abra a agenda", reply)


if __name__ == "__main__":
    unittest.main()
