import json
import unittest

from assistant_runtime.wake_word import VoskWakeWordEngine, WakeWordConfig


class FakeRecognizer:
    def __init__(self, partials: list[str]) -> None:
        self.partials = partials
        self.current = ""

    def AcceptWaveform(self, pcm16: bytes) -> bool:  # noqa: N802
        del pcm16
        self.current = self.partials.pop(0) if self.partials else ""
        return False

    def PartialResult(self) -> str:  # noqa: N802
        return json.dumps({"partial": self.current})

    def Result(self) -> str:  # noqa: N802
        return json.dumps({"text": self.current})


class WakeWordTests(unittest.TestCase):
    def test_vosk_fallback_detects_wake_from_partial_audio(self) -> None:
        engine = VoskWakeWordEngine(
            FakeRecognizer(["ola", "ola doutor"]),
            ("ola doutor",),
        )
        self.assertFalse(engine.accept(b"frame", 16_000).detected)
        result = engine.accept(b"frame", 16_000)
        self.assertTrue(result.detected)
        self.assertIsNone(result.score)
        self.assertEqual(result.engine, "vosk-fallback")

    def test_wake_config_rejects_unsafe_thresholds(self) -> None:
        with self.assertRaises(ValueError):
            WakeWordConfig(threshold=0.99)

    def test_vosk_fallback_rejects_one_frame_false_match(self) -> None:
        engine = VoskWakeWordEngine(
            FakeRecognizer(["ola doutor", ""]),
            ("ola doutor",),
            consecutive_frames=2,
        )
        self.assertFalse(engine.accept(b"frame", 16_000).detected)
        self.assertFalse(engine.accept(b"frame", 16_000).detected)

    def test_vosk_fallback_rejects_match_late_in_long_speech(self) -> None:
        engine = VoskWakeWordEngine(
            FakeRecognizer(["", "ola doutor", "ola doutor"]),
            ("ola doutor",),
            consecutive_frames=2,
            maximum_candidate_seconds=0.1,
        )
        frame = b"\0" * 3_200
        self.assertFalse(engine.accept(frame, 16_000).detected)
        self.assertFalse(engine.accept(frame, 16_000).detected)
        self.assertFalse(engine.accept(frame, 16_000).detected)


if __name__ == "__main__":
    unittest.main()
