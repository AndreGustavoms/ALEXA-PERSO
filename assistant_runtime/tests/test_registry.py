import unittest

from assistant_runtime.assistant_commands.actions import WindowsActions
from assistant_runtime.assistant_commands.models import RiskLevel, WindowContext
from assistant_runtime.assistant_commands.parser import IntentParser
from assistant_runtime.assistant_commands.registry import COMMANDS


class CommandRegistryTests(unittest.TestCase):
    def test_ids_are_unique_and_executors_exist(self) -> None:
        identifiers = [spec.id for spec in COMMANDS]

        self.assertEqual(len(identifiers), len(set(identifiers)))
        for spec in COMMANDS:
            with self.subTest(command=spec.id):
                self.assertTrue(hasattr(WindowsActions, f"do_{spec.executor}"))

    def test_destructive_registered_commands_require_confirmation(self) -> None:
        required = {
            "files.delete",
            "system.hibernate",
            "system.restart",
            "system.shutdown",
            "system.sign_out",
            "system.sleep",
        }
        risks = {spec.id: spec.risk for spec in COMMANDS}

        for command_id in required:
            self.assertEqual(risks[command_id], RiskLevel.CONFIRMATION_REQUIRED)

    def test_dangerous_fuzzy_phrase_does_not_match(self) -> None:
        parser = IntentParser()
        context = WindowContext(handle=1, kind="application")

        self.assertIsNone(parser.parse("desligado o computador", context))
        self.assertIsNone(parser.parse("reiniciando ideias", context))

    def test_out_of_range_values_are_never_executed(self) -> None:
        parser = IntentParser()
        context = WindowContext(handle=1, kind="application")

        volume = parser.parse("volume 999", context)
        brightness = parser.parse("brilho 500", context)

        self.assertEqual(volume.spec.executor, "clarify")  # type: ignore[union-attr]
        self.assertEqual(brightness.spec.executor, "clarify")  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
