import unittest
import pandas as pd
from engineer_runtime.cleaning_policy import assess_step, is_identifier


class CleaningPolicyTests(unittest.TestCase):
    def test_protect_identifiers(self):
        for name in ("customer_id", "ZIP", "account_number", "SKU", "phone"):
            self.assertTrue(is_identifier(name))

    def test_preserve_postal_codes(self):
        frame = pd.DataFrame({"zip": ["00123", "90210"]})
        allowed, _ = assess_step(frame, {"action": "cast_type", "column": "zip", "parameters": {"target_type": "number"}})
        self.assertFalse(allowed)

    def test_reject_lossy_numeric_conversion(self):
        frame = pd.DataFrame({"amount": ["10", "not available"]})
        allowed, _ = assess_step(frame, {"action": "cast_type", "column": "amount", "parameters": {"target_type": "number"}})
        self.assertFalse(allowed)

    def test_allow_lossless_numeric_conversion(self):
        frame = pd.DataFrame({"amount": ["10.5", "20", None]})
        allowed, _ = assess_step(frame, {"action": "cast_type", "column": "amount", "parameters": {"target_type": "number"}})
        self.assertTrue(allowed)

    def test_preserve_duplicates_and_outliers(self):
        frame = pd.DataFrame({"amount": [100, 100, 1000000]})
        for action in ("remove_duplicates", "clip_outliers"):
            allowed, _ = assess_step(frame, {"action": action, "column": "amount"})
            self.assertFalse(allowed)

    def test_reject_ambiguous_date(self):
        frame = pd.DataFrame({"event_date": ["01/02/2026"]})
        allowed, _ = assess_step(frame, {"action": "standardize_date", "column": "event_date"})
        self.assertFalse(allowed)


if __name__ == "__main__":
    unittest.main()
