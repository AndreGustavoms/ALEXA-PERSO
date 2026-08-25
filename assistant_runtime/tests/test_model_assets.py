import hashlib
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SILERO_MODEL = PROJECT_ROOT / "assistant_runtime" / "models" / "silero_vad.onnx"
SILERO_LICENSE = PROJECT_ROOT / "licenses" / "SILERO-VAD-LICENSE.txt"

# Documentado em docs/VOICE_PIPELINE.md: Silero VAD v6, ONNX oficial, MIT.
SILERO_MODEL_SHA256 = (
    "1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3"
)
SILERO_MODEL_SIZE_BYTES = 2_327_524


class SileroModelAssetTests(unittest.TestCase):
    """Detecta substituicao, corrupcao ou remocao do modelo/licenca distribuidos."""

    def test_model_file_exists(self) -> None:
        self.assertTrue(
            SILERO_MODEL.exists(),
            f"Modelo Silero VAD ausente em {SILERO_MODEL}.",
        )

    def test_model_size_matches_documented_value(self) -> None:
        self.assertEqual(SILERO_MODEL.stat().st_size, SILERO_MODEL_SIZE_BYTES)

    def test_model_checksum_matches_documented_value(self) -> None:
        digest = hashlib.sha256(SILERO_MODEL.read_bytes()).hexdigest()
        self.assertEqual(digest, SILERO_MODEL_SHA256)

    def test_license_notice_is_bundled(self) -> None:
        self.assertTrue(
            SILERO_LICENSE.exists(),
            f"Aviso de licenca do Silero VAD ausente em {SILERO_LICENSE}.",
        )
        text = SILERO_LICENSE.read_text(encoding="utf-8")
        self.assertIn("MIT License", text)
        self.assertIn("Silero", text)


if __name__ == "__main__":
    unittest.main()
