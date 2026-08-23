from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable

from .actions import open_resource, send_windows_app_command, start_program
from .confirmation import ConfirmationManager
from .context import WindowContextProvider
from .history import CommandHistory
from .models import CommandResult, ParsedIntent, RiskLevel, WindowContext
from .parser import IntentParser
from .router import CommandRouter
from ..platforms.factory import create_platform_actions


class CommandExecutor:
    """Facade estavel para interpretar e executar somente intencoes registradas."""

    def __init__(
        self,
        *,
        resource_opener: Callable[[str], None] = open_resource,
        program_starter: Callable[[tuple[str, ...]], None] = start_program,
        app_command_sender: Callable[[int, int], None] = send_windows_app_command,
        assistant_window_closer: Callable[[], None] | None = None,
        now_provider: Callable[[], datetime] = datetime.now,
        shortcut_roots: tuple[Path, ...] | None = None,
        shortcut_sender: Callable[[tuple[str, ...]], None] | None = None,
        text_sender: Callable[[str], None] | None = None,
        context_provider: Callable[[], WindowContext] | None = None,
        status_callback: Callable[[str], None] | None = None,
        confirmation_timeout: float = 15.0,
    ) -> None:
        del assistant_window_closer  # Mantido para compatibilidade com a API anterior.
        action_options: dict[str, object] = {
            "resource_opener": resource_opener,
            "program_starter": program_starter,
            "app_command_sender": app_command_sender,
            "now_provider": now_provider,
            "shortcut_roots": shortcut_roots,
        }
        if shortcut_sender is not None:
            action_options["shortcut_sender"] = shortcut_sender
        if text_sender is not None:
            action_options["text_sender"] = text_sender
        self.actions = create_platform_actions(**action_options)  # type: ignore[arg-type]
        self.parser = IntentParser()
        self.router = CommandRouter(self.parser)
        self.confirmations = ConfirmationManager(confirmation_timeout)
        self.history = CommandHistory()
        provider = WindowContextProvider()
        self.context_provider = context_provider or provider.current
        self.status_callback = status_callback or (lambda _status: None)

    def execute(self, transcript: str, authorized: bool) -> CommandResult:
        context = self._safe_context()
        intents = self.router.parse(
            transcript,
            context,
            previous_target=self.history.last_target(),
        )

        # A complete command always wins over a pending yes/no question. This
        # keeps phrases such as "pode fechar o YouTube" executable instead of
        # accidentally treating "pode" as confirmation.
        if intents:
            self.confirmations.discard()
            confirmation = None
        else:
            confirmation = self.confirmations.resolve(transcript)

        if confirmation is None:
            confirmation_state = "command"
        else:
            confirmation_state = confirmation.state

        if confirmation_state == "cancelled":
            return self._simple_result(
                transcript, "confirmation.cancelled", "Confirmacao cancelada",
                "Cancelado.", status="cancelled",
            )
        if confirmation_state == "expired":
            return self._simple_result(
                transcript, "confirmation.expired", "Confirmacao expirada",
                "A confirmacao expirou. Diga o comando novamente.", status="expired",
            )
        if confirmation_state == "waiting":
            return self._simple_result(
                transcript, "confirmation.waiting", "Aguardando confirmacao",
                "Responda sim para confirmar ou nao para cancelar.",
                status="awaiting_confirmation",
            )
        if (
            confirmation_state == "confirmed"
            and confirmation is not None
            and confirmation.intent
        ):
            intents = (confirmation.intent,)
        if not intents:
            self._log(transcript, None, False, "not_matched")
            return CommandResult(False, False, "")
        if len(intents) > 1:
            return self._execute_batch(transcript, intents, context, authorized)
        intent = intents[0]

        if intent.spec.executor == "clarify":
            return self._execute_intent(transcript, intent, context)

        if not authorized and intent.spec.category != "Informacao":
            response = "Reconheci o comando, mas a permissão para ações locais ainda não foi ativada."
            result = self._result(intent, False, response, "permission_required")
            self._record(transcript, intent, result)
            return result

        if intent.spec.risk == RiskLevel.BLOCKED:
            response = intent.spec.error_message or "Esse comando foi bloqueado por segurança."
            result = self._result(intent, False, response, "blocked")
            self._record(transcript, intent, result)
            return result

        if (
            intent.spec.risk == RiskLevel.CONFIRMATION_REQUIRED
            and confirmation_state != "confirmed"
        ):
            self.confirmations.request(intent)
            response = intent.spec.confirmation_prompt or "Quer mesmo fazer isso?"
            result = self._result(intent, False, response, "awaiting_confirmation")
            self._record(transcript, intent, result)
            return result

        return self._execute_intent(transcript, intent, context)

    def _execute_batch(
        self,
        transcript: str,
        intents: tuple[ParsedIntent, ...],
        context: WindowContext,
        authorized: bool,
    ) -> CommandResult:
        if not authorized:
            return CommandResult(
                True,
                False,
                "Reconheci os comandos, mas a permissao para acoes locais nao foi ativada.",
                "command.batch",
                "Comandos compostos",
                status="permission_required",
            )
        unsafe = next(
            (
                intent
                for intent in intents
                if intent.spec.risk
                in {RiskLevel.CONFIRMATION_REQUIRED, RiskLevel.BLOCKED}
            ),
            None,
        )
        if unsafe:
            if unsafe.spec.risk == RiskLevel.BLOCKED:
                return self._result(
                    unsafe,
                    False,
                    unsafe.spec.error_message or "Um dos comandos foi bloqueado.",
                    "blocked",
                )
            self.confirmations.request(unsafe)
            return self._result(
                unsafe,
                False,
                "O pedido contem uma acao sensivel. Confirme essa acao separadamente.",
                "awaiting_confirmation",
            )

        unavailable = next(
            (
                intent
                for intent in intents
                if intent.spec.id == "application.open"
                and not self.actions.apps.resolve(
                    str(intent.parameters.get("application", ""))
                )
            ),
            None,
        )
        if unavailable:
            target = unavailable.parameters.get("application", "o aplicativo")
            return self._result(
                unavailable,
                False,
                f"Nao encontrei {target}. Nenhum comando foi executado.",
                "error",
            )

        results = [
            self._execute_intent(transcript, intent, context) for intent in intents
        ]
        executed = all(result.executed for result in results)
        response = "Pronto." if executed else next(
            (result.response for result in results if not result.executed),
            "Nao consegui concluir todos os comandos.",
        )
        return CommandResult(
            matched=True,
            executed=executed,
            response=response,
            action="command.batch",
            intent_name="Comandos compostos",
            status="completed" if executed else "error",
            parameters={"actions": [result.action for result in results]},
            confidence=min(result.confidence for result in results),
        )

    def _execute_intent(
        self,
        transcript: str,
        intent: ParsedIntent,
        context: WindowContext,
    ) -> CommandResult:
        try:
            self.status_callback("executing")
            response = self.actions.execute(intent, context)
            status = (
                "confirmed"
                if intent.spec.risk == RiskLevel.CONFIRMATION_REQUIRED
                else "completed"
            )
            result = self._result(intent, True, response, status)
        except FileNotFoundError:
            logging.exception("Recurso nao encontrado para a intencao %s.", intent.spec.id)
            target = intent.parameters.get("application", "esse aplicativo")
            result = self._result(intent, False, f"Nao encontrei {target}.", "error")
        except Exception:
            logging.exception("Falha ao executar a intencao %s.", intent.spec.id)
            result = self._result(intent, False, self._friendly_error(intent), "error")
        self._record(transcript, intent, result)
        return result

    def _safe_context(self) -> WindowContext:
        try:
            return self.context_provider()
        except Exception:
            logging.exception("Nao foi possivel identificar a janela ativa.")
            return WindowContext()

    @staticmethod
    def _friendly_error(intent: ParsedIntent) -> str:
        if intent.spec.id.startswith("screen.") and "brightness" in intent.spec.id:
            return "Este computador nao permite controlar o brilho dessa forma."
        if intent.spec.executor_params.get("context") == "browser":
            return "Abra ou selecione o navegador e tente novamente."
        if intent.spec.executor_params.get("context") == "explorer":
            return "Abra ou selecione o Explorador de Arquivos e tente novamente."
        return intent.spec.error_message

    @staticmethod
    def _result(
        intent: ParsedIntent,
        executed: bool,
        response: str,
        status: str,
    ) -> CommandResult:
        return CommandResult(
            matched=True,
            executed=executed,
            response=response,
            action=intent.spec.id,
            intent_name=intent.spec.name,
            risk=intent.spec.risk,
            status=status,
            parameters=intent.parameters,
            confidence=intent.confidence,
        )

    def _simple_result(
        self,
        transcript: str,
        action: str,
        name: str,
        response: str,
        *,
        status: str,
    ) -> CommandResult:
        result = CommandResult(
            True, False, response, action, name, status=status, confidence=1.0
        )
        self.history.add(transcript, action, {}, 1.0, False, response)
        return result

    def _record(self, transcript: str, intent: ParsedIntent, result: CommandResult) -> None:
        self.history.add(
            transcript,
            intent.spec.id,
            intent.parameters,
            intent.confidence,
            result.executed,
            result.response,
        )
        self._log(transcript, intent, result.executed, result.status)

    @staticmethod
    def _log(
        transcript: str,
        intent: ParsedIntent | None,
        executed: bool,
        status: str,
    ) -> None:
        payload = {
            "transcript": transcript[:240],
            "intent": intent.spec.id if intent else None,
            "parameters": intent.parameters if intent else {},
            "confidence": intent.confidence if intent else 0.0,
            "executed": executed,
            "status": status,
        }
        logging.info(
            "command_event=%s",
            json.dumps(payload, ensure_ascii=False, default=str),
        )
