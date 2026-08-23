import unittest

from assistant_runtime.voice_activity import (
    TranscriptAccumulator,
    VoiceActivityConfig,
    VoiceActivityEvent,
    VoiceActivitySession,
)


class FakeDetector:
    def is_speech(self, frame: bytes, sample_rate: int) -> bool:
        del sample_rate
        return frame[0] == 1


class VoiceActivitySessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = VoiceActivityConfig(
            activation_start_timeout=1.0,
            speech_end_silence=0.3,
            minimum_speech_duration=0.06,
        )
        self.silence = bytes(self.config.frame_bytes)
        self.speech = bytes([1]) * self.config.frame_bytes

    def create_session(self) -> VoiceActivitySession:
        return VoiceActivitySession(self.config, FakeDetector())

    def test_times_out_only_when_speech_never_starts(self) -> None:
        session = self.create_session()
        event = VoiceActivityEvent.WAITING
        for _ in range(self.config.frames_for(self.config.activation_start_timeout)):
            event = session.accept(self.silence)
        self.assertEqual(event, VoiceActivityEvent.START_TIMEOUT)

    def test_has_no_maximum_phrase_duration(self) -> None:
        session = self.create_session()
        session.accept(self.speech)
        self.assertEqual(session.accept(self.speech), VoiceActivityEvent.SPEECH_STARTED)

        for _ in range(2_000):
            self.assertEqual(session.accept(self.speech), VoiceActivityEvent.SPEECH)

    def test_tolerates_pauses_and_ends_on_continuous_silence(self) -> None:
        session = self.create_session()
        session.accept(self.speech)
        session.accept(self.speech)

        end_frames = self.config.frames_for(self.config.speech_end_silence)
        for _ in range(end_frames - 1):
            self.assertEqual(session.accept(self.silence), VoiceActivityEvent.SPEECH)

        self.assertEqual(session.accept(self.speech), VoiceActivityEvent.SPEECH)
        for _ in range(end_frames - 1):
            self.assertEqual(session.accept(self.silence), VoiceActivityEvent.SPEECH)
        self.assertEqual(session.accept(self.silence), VoiceActivityEvent.SPEECH_ENDED)

    def test_ignores_a_short_noise_burst_before_speech(self) -> None:
        session = self.create_session()
        self.assertEqual(session.accept(self.speech), VoiceActivityEvent.WAITING)
        self.assertEqual(session.accept(self.silence), VoiceActivityEvent.WAITING)
        self.assertFalse(session.has_started)

    def test_rejects_a_fixed_maximum_phrase_duration(self) -> None:
        with self.assertRaises(ValueError):
            VoiceActivityConfig(maximum_phrase_duration=30)  # type: ignore[arg-type]

    def test_combines_recognizer_segments_across_pauses(self) -> None:
        transcript = TranscriptAccumulator()
        transcript.add("pesquisa no google por")
        transcript.add("voice activity detection")

        self.assertEqual(
            transcript.preview("em python"),
            "pesquisa no google por voice activity detection em python",
        )
        self.assertEqual(
            transcript.finish("sem cortar frases"),
            "pesquisa no google por voice activity detection sem cortar frases",
        )

    def test_removes_repeated_words_at_segment_boundary(self) -> None:
        transcript = TranscriptAccumulator()
        transcript.add("abra o youtube")
        transcript.add("youtube para mim")
        self.assertEqual(transcript.finish(), "abra o youtube para mim")


if __name__ == "__main__":
    unittest.main()
