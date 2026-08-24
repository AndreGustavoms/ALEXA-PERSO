from pathlib import Path

from PIL import Image

PROJECT_DIRECTORY = Path(__file__).resolve().parents[1]
ASSETS_DIRECTORY = PROJECT_DIRECTORY / "assets"
SOURCE_PATH = ASSETS_DIRECTORY / "doktor-assistant.png"
ICON_PATH = ASSETS_DIRECTORY / "doktor-assistant.ico"
WIZARD_PATH = ASSETS_DIRECTORY / "doktor-installer-wizard.png"
WIZARD_SMALL_PATH = ASSETS_DIRECTORY / "doktor-installer-small.png"

NAVY = (5, 9, 20, 255)


def contain(source: Image.Image, size: tuple[int, int]) -> Image.Image:
    image = source.convert("RGBA")
    image.thumbnail(size, Image.Resampling.LANCZOS)
    return image


def create_installer_art(source: Image.Image) -> None:
    wizard = Image.new("RGBA", (164, 314), NAVY)
    mark = contain(source, (132, 132))
    wizard.alpha_composite(mark, ((wizard.width - mark.width) // 2, 72))
    wizard.convert("RGB").save(WIZARD_PATH, format="PNG", optimize=True)

    small = Image.new("RGBA", (55, 55), NAVY)
    small_mark = contain(source, (47, 47))
    small.alpha_composite(
        small_mark,
        ((small.width - small_mark.width) // 2, (small.height - small_mark.height) // 2),
    )
    small.convert("RGB").save(WIZARD_SMALL_PATH, format="PNG", optimize=True)


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
        create_installer_art(source)


if __name__ == "__main__":
    create_icon()
