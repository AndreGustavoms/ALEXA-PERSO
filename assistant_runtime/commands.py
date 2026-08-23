"""Compatibilidade publica para o novo nucleo modular de comandos."""

try:
    from .assistant_commands import CommandExecutor, CommandResult, RiskLevel
    from .assistant_commands.actions import (
        open_resource,
        send_windows_app_command,
        start_program,
    )
    from .assistant_commands.normalization import normalize_text
except ImportError:  # Execucao direta de assistant_runtime/main.py.
    from assistant_commands import CommandExecutor, CommandResult, RiskLevel
    from assistant_commands.actions import (
        open_resource,
        send_windows_app_command,
        start_program,
    )
    from assistant_commands.normalization import normalize_text

__all__ = [
    "CommandExecutor",
    "CommandResult",
    "RiskLevel",
    "normalize_text",
    "open_resource",
    "send_windows_app_command",
    "start_program",
]
