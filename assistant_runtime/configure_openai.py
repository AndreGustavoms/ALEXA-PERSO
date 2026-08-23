from __future__ import annotations

import getpass
try:
    from .secret_store import save_secret
    from .app_paths import PATHS
except ImportError:
    from secret_store import save_secret
    from app_paths import PATHS


KEY_FILE = PATHS.config / "openai-key.bin"


def main() -> int:
    print("Configure a chave da OpenAI para ativar a transcricao de alta precisao.")
    print("A chave sera protegida pelo armazenamento seguro do sistema e nao aparecera na tela.")
    key = getpass.getpass("OPENAI_API_KEY: ").strip()
    if not key.startswith("sk-"):
        print("Chave invalida. Nenhuma alteracao foi feita.")
        return 1
    save_secret(KEY_FILE, key)
    print("Chave salva com protecao do sistema. Reinicie o Doktor Assistant.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
