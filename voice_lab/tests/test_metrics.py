from __future__ import annotations

import unittest

from voice_lab.benchmark import aggregate, compare_entity, compare_intent, compare_intent_kind
from voice_lab.core import classify_speech_cut, word_error_rate
from voice_lab.scoring import score_configuration


class VoiceLabMetricTests(unittest.TestCase):
    def test_word_error_rate(self) -> None:
        self.assertEqual(word_error_rate("fecha o youtube", "fecha youtube"), 1 / 3)

    def test_cut_classification(self) -> None:
        self.assertEqual(classify_speech_cut("fecha o youtube", "o youtube"), "START_CUT")
        self.assertEqual(classify_speech_cut("fecha o youtube", "fecha o"), "END_CUT")
        self.assertEqual(classify_speech_cut("fecha o youtube", "fecha o youtube"), "NONE")

    def test_unlabeled_records_do_not_create_supervised_metrics(self) -> None:
        records = [{
            "labeled": False,
            "duration_seconds": 1.0,
            "segment_count": 1,
            "boundary_risk_count": 0,
            "stt": {"wer": None, "latency_ms": 10.0, "realtime_factor": 0.01},
            "speech_cut": None,
            "intent_match": None,
            "entity_match": None,
            "end_to_end_match": None,
        }]
        metrics = aggregate(records)
        self.assertIsNone(metrics["word_error_rate"])
        self.assertIsNone(metrics["speech_cut_rate"])
        self.assertIsNone(metrics["intent_accuracy"])
        self.assertIsNone(metrics["entity_accuracy"])
        self.assertIsNone(metrics["end_to_end_accuracy"])

    def test_intent_comparison(self) -> None:
        actual = {"kind": "CLOSE_APPLICATION", "target": "youtube"}
        self.assertTrue(compare_intent(actual, actual))
        self.assertFalse(compare_intent(actual, {"kind": "OPEN_YOUTUBE"}))
        self.assertIsNone(compare_intent(actual, None))
        self.assertTrue(compare_intent_kind(actual, {"kind": "CLOSE_APPLICATION"}))
        self.assertTrue(compare_entity(actual, {"target": "youtube"}))

    def test_score_refuses_incomplete_metrics(self) -> None:
        result = score_configuration({"end_to_end_accuracy": 1.0})
        self.assertEqual(result["status"], "insufficient_data")
        self.assertIsNone(result["score"])

    def test_weighted_score_and_clipping_guardrail(self) -> None:
        metrics = {
            "end_to_end_accuracy": 1.0,
            "low_normal_voice_recall": 1.0,
            "speech_cut_rate": 0.0,
            "wake_recall": 1.0,
            "false_wake_rate": 0.0,
            "latency_score": 1.0,
            "clipping": 0.0,
        }
        self.assertEqual(score_configuration(metrics)["score"], 1.0)
        metrics["clipping"] = 0.01
        self.assertEqual(
            score_configuration(metrics)["status"], "rejected_by_guardrail"
        )


if __name__ == "__main__":
    unittest.main()
