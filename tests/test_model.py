import unittest

from mouse_jiggler.model import INT32_MAX, SettingsStore, normalize_int32


class NormalizeInt32Tests(unittest.TestCase):
    def test_regular_integer(self):
        self.assertEqual(normalize_int32("125", 10), 125)

    def test_negative_integer_uses_absolute_value(self):
        self.assertEqual(normalize_int32("-125", 10), 125)

    def test_zero_becomes_one(self):
        self.assertEqual(normalize_int32("0", 10), 1)

    def test_positive_fraction_is_truncated(self):
        self.assertEqual(normalize_int32("125.99", 10), 125)

    def test_negative_fraction_uses_absolute_then_truncates(self):
        self.assertEqual(normalize_int32("-125.99", 10), 125)

    def test_comma_is_supported(self):
        self.assertEqual(normalize_int32("12,9", 10), 12)

    def test_too_small_fraction_becomes_one(self):
        self.assertEqual(normalize_int32("0.99", 10), 1)

    def test_value_is_capped_to_int32(self):
        self.assertEqual(normalize_int32("999999999999999", 10), INT32_MAX)

    def test_empty_input_restores_previous_value(self):
        self.assertEqual(normalize_int32("", 10), 10)

    def test_incomplete_input_restores_previous_value(self):
        self.assertEqual(normalize_int32("-", 10), 10)

    def test_non_finite_input_restores_previous_value(self):
        self.assertEqual(normalize_int32("NaN", 10), 10)


class SettingsStoreTests(unittest.TestCase):
    def test_update_does_not_reset_other_values(self):
        store = SettingsStore()
        store.update(move_interval_ms=2500, distance=25)
        store.update(return_cursor=False)

        settings = store.snapshot()
        self.assertEqual(settings.move_interval_ms, 2500)
        self.assertEqual(settings.distance, 25)
        self.assertFalse(settings.return_cursor)


if __name__ == "__main__":
    unittest.main()
