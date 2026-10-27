import unittest
import pandas as pd
from engineer_runtime.cleaning_review import fingerprint, review_plan, approved_steps, validate_result, audit_record, preview_plan

class ReviewTests(unittest.TestCase):
    def test_review_and_preview(self):
        df = pd.DataFrame({'amount': ['10', '20']})
        step = {'action': 'cast_type', 'column': 'amount', 'parameters': {'target_type': 'number'}}
        self.assertEqual(review_plan(df, [step])[0]['decision'], 'auto')
        self.assertTrue(preview_plan(df, [step])['source_unchanged'])
        self.assertEqual(fingerprint(step), fingerprint(dict(step)))

    def test_approval_cannot_bypass_safety(self):
        df = pd.DataFrame({'amount': [10, 10]})
        step = {'action': 'remove_duplicates', 'column': None}
        accepted, deferred = approved_steps(df, [step], [fingerprint(step)])
        self.assertEqual(len(accepted), 0)
        self.assertEqual(len(deferred), 1)
        self.assertTrue(validate_result(df, df, [])['columns_preserved'])
        self.assertIn('run_id', audit_record([step], [], {}))
