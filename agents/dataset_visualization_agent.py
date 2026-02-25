import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, Any

class DatasetVisualizationAgent:
    """
    Generates basic EDA charts from the dataset:
    - Null heatmap
    - Numeric distributions
    - Top-K categorical value bars
    """

    def __init__(self, dataset_path: str, output_dir: str = "outputs/charts"):
        self.dataset_path = dataset_path
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def run(self) -> Dict[str, Any]:
        df = pd.read_csv(self.dataset_path)

        charts = []

        # -----------------------------
        # 1) Nulls heatmap
        # -----------------------------
        plt.figure(figsize=(10, 6))
        sns.heatmap(df.isna(), cbar=False)
        plt.title("Null Values Heatmap")
        nulls_path = os.path.join(self.output_dir, "nulls.png")
        plt.tight_layout()
        plt.savefig(nulls_path)
        plt.close()
        charts.append(("Nulls Heatmap", nulls_path))

        # -----------------------------
        # 2) Numeric distributions
        # -----------------------------
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        for col in numeric_cols[:5]:  # limit to first 5 to avoid explosion
            plt.figure(figsize=(8, 5))
            sns.histplot(df[col].dropna(), kde=True)
            plt.title(f"Distribution of {col}")
            path = os.path.join(self.output_dir, f"dist_{col}.png")
            plt.tight_layout()
            plt.savefig(path)
            plt.close()
            charts.append((f"Distribution of {col}", path))

        # -----------------------------
        # 3) Categorical top-K
        # -----------------------------
        categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
        for col in categorical_cols[:5]:
            plt.figure(figsize=(8, 5))
            vc = df[col].value_counts().head(10)
            sns.barplot(x=vc.values, y=vc.index)
            plt.title(f"Top values of {col}")
            path = os.path.join(self.output_dir, f"topk_{col}.png")
            plt.tight_layout()
            plt.savefig(path)
            plt.close()
            charts.append((f"Top values of {col}", path))

        # -----------------------------
        # Build Markdown index
        # -----------------------------
        md_lines = ["# 📊 Dataset Visualization Report\n"]
        md_lines.append("The following charts were automatically generated from the uploaded dataset:\n")

        for title, path in charts:
            rel_path = path.replace("\\", "/")
            md_lines.append(f"## {title}\n")
            md_lines.append(f"![{title}]({rel_path})\n")

        md = "\n".join(md_lines)

        return {
            "markdown": md,
            "charts": charts
        }