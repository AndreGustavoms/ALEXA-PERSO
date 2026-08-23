from pathlib import Path

from PIL import Image

PROJECT_DIRECTORY = Path(__file__).resolve().parents[1]
ASSETS_DIRECTORY = PROJECT_DIRECTORY / "assets"
SOURCE_PATH = ASSETS_DIRECTORY / "doktor-assistant.png"
ICON_PATH = ASSETS_DIRECTORY / "doktor-assistant.ico"


def create_icon() -> None:
    ASSETS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    with Image.open(SOURCE_PATH) as source:
        source.convert("RGBA").save(
            ICON_PATH,
            format="ICO",
            sizes=[
                (16, 16),
                (24, 24),
                (32, 32),
                (48, 48),
                (64, 64),
                (128, 128),
                (256, 256),
            ],
        )


if __name__ == "__main__":
    create_icon()
