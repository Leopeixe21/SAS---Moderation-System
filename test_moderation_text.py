import unittest

from moderation_text import split_reason_observation


class SplitReasonObservationTest(unittest.TestCase):
    def test_splits_accented_observation(self) -> None:
        self.assertEqual(
            split_reason_observation("Quebra de regra. Observação: Houve reincidência."),
            ("Quebra de regra.", "Houve reincidência."),
        )

    def test_accepts_bold_marker_without_accent(self) -> None:
        self.assertEqual(
            split_reason_observation("Spam\n**Observacao**: três mensagens seguidas"),
            ("Spam", "três mensagens seguidas"),
        )

    def test_keeps_regular_reason_unchanged(self) -> None:
        self.assertEqual(split_reason_observation("Você é feio"), ("Você é feio", None))

    def test_ignores_empty_observation(self) -> None:
        self.assertEqual(split_reason_observation("Spam Observação:"), ("Spam Observação:", None))


if __name__ == "__main__":
    unittest.main()
