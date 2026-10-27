"""Integration checks for the workspace, local-only model fallback and data contracts."""
import os
import tempfile
import unittest
from pathlib import Path

os.environ["MODEL_PROVIDER"] = "deterministic"

import pandas as pd
from fastapi.testclient import TestClient
from app import app
from agents.engineer_agents.cleaning_planner_agent import CleaningPlannerAgent
from data_access.loaders import load_dataset
from engineer_runtime.cleaning_pipeline import run_cleaning_pipeline


class WorkspaceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_workspace_pages_and_styles(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/clean").status_code, 200)
        style = self.client.get("/static/studio.css")
        self.assertEqual(style.status_code, 200)
        self.assertIn("Studio", style.text)

    def test_private_endpoints_and_static_files(self):
        self.assertEqual(self.client.get("/session-debug").status_code, 404)
        self.assertEqual(self.client.get("/outputs/cleaner/cleaned_files/secret.csv").status_code, 404)
        self.assertEqual(self.client.get("/download-cleaned-dataset").status_code, 404)
        self.assertEqual(self.client.get("/outputs/analyst/analysis_report.json").status_code, 404)
        self.assertNotEqual(self.client.post("/set-shared-dataset", data={"dataset_path": "app.py"}).status_code, 200)

    def test_csv_preserves_identifiers_and_literal_missing_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.csv"
            path.write_text("postal_code,amount,status\\n00123,10,NULL\\n90210,20,UNKNOWN\\n", encoding="utf-8")
            # Use real newlines in the test fixture
            path.write_text("postal_code,amount,status\n00123,10,NULL\n90210,20,UNKNOWN\n", encoding="utf-8")
            df = load_dataset(str(path)).dataframe
            self.assertEqual(str(df.loc[0, "postal_code"]), "00123")
            self.assertEqual(df.loc[0, "status"], "NULL")
            self.assertEqual(df.loc[1, "status"], "UNKNOWN")

    def test_deterministic_cleaning_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.csv"
            path.write_text("customer_id,amount,region\n001,10,North\n002,20,north\n003,,North\n", encoding="utf-8")
            result = run_cleaning_pipeline(str(path), "Do not edit customer IDs")
            self.assertEqual(result["status"], "success")
            self.assertIn("cleaning_preview", result)
            self.assertIn("cleaning_validation", result)
            self.assertIn("cleaning_audit", result)
            self.assertEqual(result["rows_after_cleaning"], 3)
            self.assertTrue(Path(result["cleaned_file_path"]).exists())

    def test_cleaner_post_renders_review_and_private_download(self):
        payload = b"customer_id,amount,region\\n001,10,North\\n002,20,South\\n"
        payload = payload.replace(b"\\n", b"\n")
        response = self.client.post(
            "/clean", files={"dataset": ("sample.csv", payload, "text/csv")},
            data={"business_requirements": "Preserve identifiers"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Transformation review", response.text)
        self.assertIn("/download-cleaned-dataset", response.text)
        self.assertEqual(self.client.get("/download-cleaned-dataset").status_code, 200)

    def test_no_provider_credentials_required(self):
        planner = CleaningPlannerAgent()
        self.assertIsNone(planner.llm)


if __name__ == "__main__":
    unittest.main()
