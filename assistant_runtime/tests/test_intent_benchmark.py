import unittest
from pathlib import Path

from assistant_runtime.intent_benchmark import load_corpus, run_benchmark


CORPUS = Path(__file__).parent / "utterances" / "intent_corpus.jsonl"


class IntentBenchmarkTests(unittest.TestCase):
    def test_corpus_is_large_and_contains_negative_cases(self) -> None:
        records = load_corpus(CORPUS)

        self.assertGreaterEqual(len(records), 100)
        self.assertGreaterEqual(
            sum(record.get("intent") == "NONE" for record in records),
            15,
        )

    def test_intent_quality_gate(self) -> None:
        result = run_benchmark(CORPUS)

        self.assertGreaterEqual(result.intent_accuracy, 0.97, result.failures)
        self.assertGreaterEqual(result.entity_accuracy, 0.97, result.failures)
        self.assertLessEqual(result.negative_false_positive_rate, 0.01, result.failures)


if __name__ == "__main__":
    unittest.main()
