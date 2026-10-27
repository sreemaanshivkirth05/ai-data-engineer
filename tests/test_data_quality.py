import unittest
import pandas as pd
from engineer_runtime.data_quality import diagnose_column, diagnose_dataframe


class DataQualityTests(unittest.TestCase):
    def test_postal_preserved(self):
        result = diagnose_column("postal_code", pd.Series(["00123", "90210"]))
        self.assertTrue(result["protected"])

    def test_ambiguous_dates_flagged(self):
        result = diagnose_column("order_date", pd.Series(["01/02/2026", "2026-12-31"]))
        self.assertEqual(result["issues"][0]["type"], "ambiguous_date")

    def test_boolean_recognized(self):
        self.assertEqual(diagnose_column("active", pd.Series([True, False]))["semantic_hint"], "boolean")

    def test_email_format_diagnostic(self):
        result = diagnose_column("contact_email", pd.Series(["x@example.com", "not-an-email"]))
        self.assertEqual(result["issues"][0]["count"], 1)

    def test_no_mutation(self):
        df = pd.DataFrame({"order_date": ["01/02/2026"], "zip": ["00123"]})
        before = df.copy(deep=True)
        diagnose_dataframe(df)
        pd.testing.assert_frame_equal(df, before)

    def test_empty_column(self):
        self.assertEqual(diagnose_column("notes", pd.Series([None, None]))["semantic_hint"], "empty")


if __name__ == "__main__":
    unittest.main()
