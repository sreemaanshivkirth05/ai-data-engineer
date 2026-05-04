import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

import pandas as pd


SUPPORTED_FORMATS = {
    ".csv": "csv",
    ".tsv": "tsv",
    ".xlsx": "xlsx",
    ".xls": "xlsx",
    ".json": "json",
    ".jsonl": "jsonl",
    ".ndjson": "jsonl",
    ".parquet": "parquet",
}


@dataclass
class DatasetBundle:
    dataframe: pd.DataFrame
    source_path: str
    dataset_format: str
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


def infer_dataset_format(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in SUPPORTED_FORMATS:
        return SUPPORTED_FORMATS[ext]
    raise ValueError(
        f"Unsupported dataset format: {ext}. "
        f"Supported formats: {sorted(SUPPORTED_FORMATS.keys())}"
    )


def _flatten_json_records(obj: Any) -> Tuple[pd.DataFrame, Dict[str, Any], List[str]]:
    warnings: List[str] = []
    metadata: Dict[str, Any] = {}

    if isinstance(obj, list):
        if all(isinstance(x, dict) for x in obj):
            df = pd.json_normalize(obj)
            metadata["json_root"] = "top_level_list"
            return df, metadata, warnings

    if isinstance(obj, dict):
        candidate_tables = []
        for key, value in obj.items():
            if isinstance(value, list) and value and all(isinstance(x, dict) for x in value):
                candidate_tables.append((key, value))

        if len(candidate_tables) == 1:
            key, value = candidate_tables[0]
            df = pd.json_normalize(value)
            metadata["json_root"] = key
            return df, metadata, warnings

        if len(candidate_tables) > 1:
            key, value = max(candidate_tables, key=lambda item: len(item[1]))
            df = pd.json_normalize(value)
            metadata["json_root"] = key
            metadata["json_candidate_roots"] = [k for k, _ in candidate_tables]
            warnings.append(
                f"Multiple JSON tables detected. Automatically selected '{key}' "
                f"from {metadata['json_candidate_roots']}."
            )
            return df, metadata, warnings

        df = pd.json_normalize(obj)
        metadata["json_root"] = "top_level_object"
        warnings.append(
            "JSON did not contain a clear list-of-records table. Flattened top-level object into one row."
        )
        return df, metadata, warnings

    raise ValueError("Could not parse JSON into a tabular structure.")


def load_dataframe(path: str) -> pd.DataFrame:
    return load_dataset(path).dataframe


def load_dataset(path: str) -> DatasetBundle:
    dataset_format = infer_dataset_format(path)
    warnings: List[str] = []
    metadata: Dict[str, Any] = {}

    if dataset_format == "csv":
        df = pd.read_csv(path)

    elif dataset_format == "tsv":
        df = pd.read_csv(path, sep="\t")

    elif dataset_format == "xlsx":
        excel_file = pd.ExcelFile(path)
        metadata["sheet_names"] = excel_file.sheet_names

        if not excel_file.sheet_names:
            raise ValueError("Excel file does not contain any sheets.")

        selected_sheet = excel_file.sheet_names[0]
        df = pd.read_excel(path, sheet_name=selected_sheet)
        metadata["selected_sheet"] = selected_sheet

        if len(excel_file.sheet_names) > 1:
            warnings.append(
                f"Multiple Excel sheets detected. Automatically selected '{selected_sheet}'."
            )

    elif dataset_format == "json":
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        df, json_meta, json_warnings = _flatten_json_records(obj)
        metadata.update(json_meta)
        warnings.extend(json_warnings)

    elif dataset_format == "jsonl":
        records = []
        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    records.append(json.loads(stripped))
                except json.JSONDecodeError:
                    warnings.append(f"Skipped invalid JSONL line {line_no}.")
        if not records:
            raise ValueError("JSONL file did not contain any valid records.")
        df = pd.json_normalize(records)

    elif dataset_format == "parquet":
        df = pd.read_parquet(path)

    else:
        raise ValueError(f"Unsupported dataset format: {dataset_format}")

    if not isinstance(df, pd.DataFrame):
        raise ValueError("Loaded dataset is not a valid dataframe.")

    if len(df.columns) == 0:
        raise ValueError("Loaded dataset has no columns.")

    metadata["row_count"] = int(len(df))
    metadata["column_count"] = int(len(df.columns))

    return DatasetBundle(
        dataframe=df,
        source_path=path,
        dataset_format=dataset_format,
        warnings=warnings,
        metadata=metadata,
    )


def save_dataframe(df: pd.DataFrame, output_path: str) -> str:
    ext = os.path.splitext(output_path)[1].lower()

    if ext == ".csv":
        df.to_csv(output_path, index=False)
        return output_path

    if ext in {".xlsx", ".xls"}:
        df.to_excel(output_path, index=False)
        return output_path

    if ext == ".json":
        df.to_json(output_path, orient="records", indent=2)
        return output_path

    if ext in {".jsonl", ".ndjson"}:
        df.to_json(output_path, orient="records", lines=True)
        return output_path

    if ext == ".parquet":
        df.to_parquet(output_path, index=False)
        return output_path

    fallback = output_path + ".csv"
    df.to_csv(fallback, index=False)
    return fallback