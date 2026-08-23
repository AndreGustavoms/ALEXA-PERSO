import os
import time
import unittest
from unittest import mock
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from assistant_runtime.assistant_commands.models import WindowContext
from assistant_runtime.commands import CommandExecutor


@unittest.skipUnless(os.name == "nt", "Integracao de acoes Windows")
class CommandExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.resources: list[str] = []
        self.programs: list[tuple[str, ...]] = []
        self.media_commands: list[tuple[int, int]] = []
        self.shortcuts: list[tuple[str, ...]] = []
        self.typed_text: list[str] = []
        self.context = WindowContext(
            handle=100,
            process_id=10,
            process_name="chrome.exe",
            title="Exemplo - Google Chrome",
            application="Chrome",
            kind="browser",
        )
        self.executor = CommandExecutor(
            resource_opener=self.resources.append,
            program_starter=self.programs.append,
            app_command_sender=lambda command, repeats: self.media_commands.append(
                (command, repeats)
            ),
            shortcut_sender=self.shortcuts.append,
            text_sender=self.typed_text.append,
            context_provider=lambda: self.context,
            now_provider=lambda: datetime(2026, 8, 23, 14, 35),
            shortcut_roots=(),
        )

    def test_opens_youtube_from_natural_request(self) -> None:
        result = self.executor.execute(
            "bom, eu queria que você abrir o YouTube para mim",
            authorized=True,
        )

        self.assertTrue(result.executed)
        self.assertEqual(result.action, "browser.open_site")
        self.assertEqual(self.resources, ["https://www.youtube.com"])

    def test_blocks_action_until_permission_is_accepted(self) -> None:
        result = self.executor.execute("abra a calculadora", authorized=False)

        self.assertTrue(result.matched)
        self.assertFalse(result.executed)
        self.assertEqual(self.programs, [])
        self.assertIn("permissão", result.response)

    def test_builds_youtube_search(self) -> None:
        result = self.executor.execute(
            "pesquisar música brasileira no YouTube",
            authorized=True,
        )

        self.assertTrue(result.executed)
        self.assertEqual(
            self.resources,
            ["https://www.youtube.com/results?search_query=musica+brasileira"],
        )

    def test_sensitive_action_requires_confirmation(self) -> None:
        pending = self.executor.execute("desligar o computador", authorized=True)

        self.assertFalse(pending.executed)
        self.assertEqual(pending.action, "system.shutdown")
        self.assertEqual(pending.status, "awaiting_confirmation")
        self.assertEqual(self.programs, [])

        confirmed = self.executor.execute("sim", authorized=True)
        self.assertTrue(confirmed.executed)
        self.assertEqual(confirmed.status, "confirmed")
        self.assertEqual(self.programs, [("shutdown.exe", "/s", "/t", "0")])

    def test_pending_action_can_be_cancelled(self) -> None:
        self.executor.execute("reinicia o computador", authorized=True)
        cancelled = self.executor.execute("deixa quieto", authorized=True)

        self.assertEqual(cancelled.status, "cancelled")
        self.assertEqual(self.programs, [])

    def test_confirmation_expires(self) -> None:
        executor = CommandExecutor(
            program_starter=self.programs.append,
            shortcut_sender=self.shortcuts.append,
            context_provider=lambda: self.context,
            shortcut_roots=(),
            confirmation_timeout=0.01,
        )
        executor.execute("desliga o computador", authorized=True)
        time.sleep(0.02)

        result = executor.execute("sim", authorized=True)

        self.assertEqual(result.status, "expired")
        self.assertEqual(self.programs, [])

    def test_answers_time_without_permission(self) -> None:
        result = self.executor.execute("que horas são", authorized=False)

        self.assertTrue(result.executed)
        self.assertEqual(result.response, "Agora são 14:35.")

    def test_page_means_browser_tab_not_browser_process(self) -> None:
        result = self.executor.execute("feche esta página", authorized=True)

        self.assertTrue(result.executed)
        self.assertEqual(result.action, "browser.close_tab")
        self.assertEqual(self.shortcuts, [("CTRL", "W")])
        self.assertEqual(self.programs, [])

    def test_page_is_not_treated_as_an_application_outside_browser(self) -> None:
        self.context = WindowContext(handle=200, process_name="code.exe", kind="application")

        result = self.executor.execute("fecha essa página", authorized=True)

        self.assertFalse(result.matched)
        self.assertEqual(self.shortcuts, [])

    def test_opens_installed_app_from_start_menu_shortcut(self) -> None:
        with TemporaryDirectory() as directory:
            shortcut = Path(directory) / "Agenda Local.lnk"
            shortcut.touch()
            executor = CommandExecutor(
                resource_opener=self.resources.append,
                program_starter=self.programs.append,
                shortcut_sender=self.shortcuts.append,
                context_provider=lambda: self.context,
                shortcut_roots=(Path(directory),),
            )

            result = executor.execute("abra a Agenda Local", authorized=True)

            self.assertTrue(result.executed)
            self.assertEqual(self.resources, [str(shortcut)])

    def test_unknown_text_is_never_executed_as_shell(self) -> None:
        result = self.executor.execute(
            "powershell remove item c dois pontos barra usuarios",
            authorized=True,
        )

        self.assertFalse(result.matched)
        self.assertEqual(self.programs, [])
        self.assertEqual(self.shortcuts, [])

    def test_types_text_and_presses_enter_in_the_active_window(self) -> None:
        typed = self.executor.execute("escreve meu nome aqui", authorized=True)
        entered = self.executor.execute("aperta enter", authorized=True)

        self.assertTrue(typed.executed)
        self.assertEqual(typed.action, "keyboard.type_text")
        self.assertEqual(self.typed_text, ["meu nome aqui"])
        self.assertTrue(entered.executed)
        self.assertEqual(self.shortcuts, [("ENTER",)])

    def test_routes_and_executes_compound_command_in_order(self) -> None:
        result = self.executor.execute(
            "fecha o YouTube e depois abre o GitHub",
            authorized=True,
        )

        self.assertTrue(result.executed)
        self.assertEqual(result.action, "command.batch")
        self.assertEqual(self.shortcuts, [("CTRL", "W")])
        self.assertEqual(self.resources, ["https://github.com"])
        self.assertEqual(result.parameters["actions"], [
            "browser.close_tab",
            "browser.open_site",
        ])

    def test_launches_valorant_through_riot_client(self) -> None:
        with mock.patch.object(
            self.executor.actions.apps,
            "resolve",
            return_value=("Valorant", (r"C:\Riot Games\Riot Client\RiotClientServices.exe",)),
        ):
            result = self.executor.execute("abre o valor antes", authorized=True)

        self.assertTrue(result.executed)
        self.assertEqual(
            self.programs[-1],
            (
                r"C:\Riot Games\Riot Client\RiotClientServices.exe",
                "--launch-product=valorant",
                "--launch-patchline=live",
            ),
        )

    def test_never_partially_executes_unrecognized_compound_command(self) -> None:
        result = self.executor.execute(
            "abre o YouTube e depois abre o teletransportador quantum",
            authorized=True,
        )

        self.assertFalse(result.executed)
        self.assertEqual(self.resources, [])


if __name__ == "__main__":
    unittest.main()
