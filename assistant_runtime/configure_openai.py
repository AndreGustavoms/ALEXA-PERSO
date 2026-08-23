from __future__ import annotations

import getpass
from pathlib import Path

try:
    from .secret_store import save_secret
except ImportError:
    from secret_store import save_secret


PROJECT_DIRECTORY = Path(__file__).resolve().parents[1]
KEY_FILE = PROJECT_DIRECTORY / "runtime" / "config" / "openai-key.bin"


def main() -> int:
    print("Configure a chave da OpenAI para ativar a transcricao de alta precisao.")
    print("A chave sera protegida pela sua conta do Windows e nao aparecera na tela.")
    key = getpass.getpass("OPENAI_API_KEY: ").strip()
    if not key.startswith("sk-"):
        print("Chave invalida. Nenhuma alteracao foi feita.")
        return 1
    save_secret(KEY_FILE, key)
    print("Chave salva com protecao do Windows. Reinicie o Doktor Assistant.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
