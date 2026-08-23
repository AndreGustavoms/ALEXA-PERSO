import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from assistant_runtime.voice_metrics import VoiceMetrics


class VoiceMetricsTests(unittest.TestCase):
    def test_persists_only_aggregate_voice_metrics(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "metrics.json"
            metrics = VoiceMetrics(path)
            metrics.activation()
            metrics.transcription(
                provider="vosk-local",
                audio_seconds=2.4,
                latency_ms=730,
            )

            restored = VoiceMetrics(path).snapshot()
            self.assertEqual(restored["activations"], 1)
            self.assertEqual(restored["audioSeconds"], 2.4)
            self.assertEqual(restored["lastLatencyMs"], 730)
            self.assertNotIn("audio", restored)


if __name__ == "__main__":
    unittest.main()
