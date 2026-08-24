import unittest
from array import array

from assistant_runtime.voice_activity import (
    AudioPreprocessor,
    AudioPreRollBuffer,
    TranscriptAccumulator,
    VoiceActivityConfig,
    VoiceActivityEvent,
    VoiceActivitySession,
    normalize_pcm16,
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
            possible_end_silence=0.1,
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

        end_frames = self.config.frames_for(
            self.config.speech_end_silence + self.config.end_padding_duration
        )
        for _ in range(end_frames - 1):
            self.assertNotEqual(session.accept(self.silence), VoiceActivityEvent.SPEECH_ENDED)

        self.assertEqual(session.accept(self.speech), VoiceActivityEvent.SPEECH)
        for _ in range(end_frames - 1):
            self.assertNotEqual(session.accept(self.silence), VoiceActivityEvent.SPEECH_ENDED)
        self.assertEqual(session.accept(self.silence), VoiceActivityEvent.SPEECH_ENDED)

    def test_emits_possible_end_once_and_recovers_when_speech_returns(self) -> None:
        session = self.create_session()
        session.accept(self.speech)
        session.accept(self.speech)
        events = [
            session.accept(self.silence)
            for _ in range(self.config.frames_for(self.config.possible_end_silence))
        ]
        self.assertEqual(events.count(VoiceActivityEvent.POSSIBLE_END), 1)
        self.assertEqual(session.accept(self.speech), VoiceActivityEvent.SPEECH)

    def test_default_turn_tolerates_a_one_and_a_half_second_pause(self) -> None:
        config = VoiceActivityConfig()
        silence = bytes(config.frame_bytes)
        speech = bytes([1]) * config.frame_bytes
        session = VoiceActivitySession(config, FakeDetector())
        session.accept(speech)
        session.accept(speech)
        for _ in range(config.frames_for(1.5)):
            self.assertNotEqual(session.accept(silence), VoiceActivityEvent.SPEECH_ENDED)
        self.assertEqual(session.accept(speech), VoiceActivityEvent.SPEECH)

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

    def test_default_voice_detection_accepts_quiet_speech_quickly(self) -> None:
        config = VoiceActivityConfig()

        self.assertEqual(config.vad_aggressiveness, 0)
        self.assertEqual(config.sensitivity_preset, "VERY_HIGH")
        self.assertEqual(config.minimum_speech_duration, 0.06)
        self.assertEqual(config.maximum_input_gain, 10.0)
        self.assertEqual(config.frames_for(config.minimum_speech_duration), 2)

    def test_normalizes_quiet_pcm_without_clipping(self) -> None:
        samples = array("h", [100, -200, 400, -600])
        normalized = array("h")
        normalized.frombytes(normalize_pcm16(samples.tobytes(), 10.0))

        self.assertEqual(normalized.tolist(), [1000, -2000, 4000, -6000])

    def test_loud_pcm_is_not_amplified_past_target(self) -> None:
        samples = array("h", [20_000, -20_000])

        self.assertEqual(normalize_pcm16(samples.tobytes(), 10.0), samples.tobytes())

    def test_rejects_invalid_input_gain(self) -> None:
        with self.assertRaises(ValueError):
            VoiceActivityConfig(maximum_input_gain=21.0)

    def test_pre_roll_keeps_only_the_latest_audio_window(self) -> None:
        config = VoiceActivityConfig(pre_roll_duration=0.3)
        buffer = AudioPreRollBuffer(config)
        for value in range(config.frames_for(0.6)):
            buffer.append(bytes([value % 256]) * config.frame_bytes)
        snapshot = buffer.snapshot()
        self.assertEqual(len(snapshot), config.frames_for(0.3))
        self.assertEqual(snapshot[-1][0], config.frames_for(0.6) - 1)

    def test_adaptive_preprocessor_lifts_quiet_voice_without_clipping(self) -> None:
        preprocessor = AudioPreprocessor(maximum_gain=10.0)
        quiet = array("h", [250, -300, 400, -450] * 120).tobytes()
        processed, metrics = preprocessor.process(quiet)
        self.assertGreater(metrics.processed_rms, metrics.raw_rms)
        self.assertLessEqual(metrics.gain, 10.0)
        self.assertEqual(metrics.clipping, 0.0)
        self.assertNotEqual(processed, quiet)

    def test_fifty_turns_reset_without_leaking_state(self) -> None:
        for _ in range(50):
            session = self.create_session()
            session.accept(self.speech)
            self.assertEqual(session.accept(self.speech), VoiceActivityEvent.SPEECH_STARTED)
            end_frames = self.config.frames_for(
                self.config.speech_end_silence + self.config.end_padding_duration
            )
            event = VoiceActivityEvent.SPEECH
            for _ in range(end_frames):
                event = session.accept(self.silence)
            self.assertEqual(event, VoiceActivityEvent.SPEECH_ENDED)


if __name__ == "__main__":
    unittest.main()
