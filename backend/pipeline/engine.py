import re
import time
from pathlib import Path
from typing import Any

import pandas as pd

from ..database import UPLOAD_DIR


class NodeExecutionError(Exception):
    def __init__(self, node: dict, error: Exception, results: list, logs: list, duration_ms: int):
        super().__init__(str(error))
        self.node = node
        self.results = results
        self.logs = logs
        self.duration_ms = duration_ms


def serial(value: Any):
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def preview(df: pd.DataFrame, errors: list | None = None) -> dict:
    rows = [{k: serial(v) for k, v in row.items()} for row in df.head(100).to_dict("records")]
    return {
        "rows": rows,
        "rowCount": len(df),
        "columnCount": len(df.columns),
        "columns": [
            {
                "name": str(c),
                "type": str(df[c].dtype),
                "nullCount": int(df[c].isna().sum()),
                "nullPercent": round(float(df[c].isna().mean() * 100), 2),
                "distinctCount": int(df[c].nunique(dropna=True)),
            }
            for c in df.columns
        ],
        "duplicateCount": int(df.duplicated().sum()),
        "errors": errors or [],
    }


class PipelineEngine:
    """Stateless node runner. Add operations by registering a method in handlers."""

    def __init__(self):
        self.frames: dict[str, pd.DataFrame] = {}
        self.validation_errors = 0

    def load(self, config: dict) -> pd.DataFrame:
        path = (UPLOAD_DIR / Path(config["storedName"]).name).resolve()
        if not path.is_relative_to(UPLOAD_DIR.resolve()):
            raise ValueError("Invalid input path")
        ext = path.suffix.lower()
        if ext == ".csv":
            return pd.read_csv(path)
        if ext == ".tsv":
            return pd.read_csv(path, sep="\t")
        if ext == ".xlsx":
            return pd.read_excel(path, sheet_name=config.get("sheet", 0))
        if ext == ".parquet":
            return pd.read_parquet(path)
        raise ValueError(f"Unsupported file type: {ext}")

    def execute_node(self, node: dict, current: pd.DataFrame | None) -> tuple[pd.DataFrame, list]:
        kind, c = node["type"], node.get("config", {})
        errors: list = []
        if kind == "input":
            result = self.load(c)
            self.frames[node["id"]] = result
            return result, errors
        if current is None:
            raise ValueError("Add an input before transformations")
        result = current.copy()
        if kind == "keep_columns":
            result = result[c.get("columns", [])]
        elif kind == "remove_columns":
            result = result.drop(columns=c.get("columns", []), errors="ignore")
        elif kind == "rename_columns":
            result = result.rename(columns=c.get("mapping", {}))
        elif kind == "filter":
            column, op, value = c.get("column"), c.get("operator", "equals"), c.get("value")
            s = result[column]
            if op == "equals": mask = s.astype(str) == str(value)
            elif op == "not_equals": mask = s.astype(str) != str(value)
            elif op == "contains": mask = s.astype(str).str.contains(str(value), case=False, na=False)
            elif op == "greater": mask = pd.to_numeric(s, errors="coerce") > float(value)
            elif op == "less": mask = pd.to_numeric(s, errors="coerce") < float(value)
            elif op == "is_null": mask = s.isna()
            elif op == "not_null": mask = s.notna()
            else: raise ValueError(f"Unsupported filter operator: {op}")
            result = result[mask]
        elif kind == "sort":
            result = result.sort_values(c.get("columns", []), ascending=c.get("ascending", True))
        elif kind == "remove_duplicates":
            result = result.drop_duplicates(subset=c.get("columns") or None)
        elif kind == "fill_null":
            result[c["column"]] = result[c["column"]].fillna(c.get("value", ""))
        elif kind == "case":
            col = c["column"]
            result[col] = getattr(result[col].astype(str).str, c.get("mode", "upper"))()
        elif kind == "calculated":
            result[c["name"]] = result.eval(c["expression"])
        elif kind == "top_n":
            result = result.head(int(c.get("count", 100)))
        elif kind == "aggregate":
            result = result.groupby(c.get("groupBy", []), dropna=False).agg(c.get("aggregations", {})).reset_index()
        elif kind == "validation":
            column, rule = c.get("column"), c.get("rule", "null")
            if rule == "null":
                invalid = result[column].isna()
            elif rule == "unique":
                invalid = result[column].duplicated(keep=False)
            elif rule == "regex":
                invalid = ~result[column].astype(str).str.match(c.get("pattern", ".*"), na=False)
            elif rule == "range":
                values = pd.to_numeric(result[column], errors="coerce")
                invalid = ~values.between(float(c.get("min", "-inf")), float(c.get("max", "inf")))
            elif rule == "allowed":
                invalid = ~result[column].isin(c.get("values", []))
            else:
                invalid = pd.Series(False, index=result.index)
            errors = [
                {"row": int(i), "column": column, "reason": c.get("message") or f"Failed {rule} validation"}
                for i in result.index[invalid][:100]
            ]
            self.validation_errors += int(invalid.sum())
        else:
            raise ValueError(f"Node type '{kind}' is not implemented")
        self.frames[node["id"]] = result
        return result, errors

    def run(self, nodes: list[dict]) -> dict:
        started, current, results, logs = time.perf_counter(), None, [], []
        for index, node in enumerate(nodes):
            tick = time.perf_counter()
            try:
                current, errors = self.execute_node(node, current)
            except Exception as exc:
                elapsed = int((time.perf_counter() - tick) * 1000)
                results.append({
                    "nodeId": node["id"], "name": node.get("name", node["type"]),
                    "status": "failed", "durationMs": elapsed, "error": str(exc),
                    "rows": [], "rowCount": 0, "columnCount": 0, "columns": [],
                    "duplicateCount": 0, "errors": [{"reason": str(exc)}],
                })
                logs.append(f"{index + 1}. {node.get('name', node['type'])}: FAILED — {exc}")
                raise NodeExecutionError(
                    node, exc, results, logs, int((time.perf_counter() - started) * 1000)
                ) from exc
            elapsed = int((time.perf_counter() - tick) * 1000)
            results.append({"nodeId": node["id"], "name": node.get("name", node["type"]), "status": "success", "durationMs": elapsed, **preview(current, errors)})
            logs.append(f"{index + 1}. {node.get('name', node['type'])}: {len(current):,} rows in {elapsed}ms")
        return {
            "durationMs": int((time.perf_counter() - started) * 1000),
            "outputRows": 0 if current is None else len(current),
            "validationErrors": self.validation_errors,
            "nodeResults": results,
            "log": logs,
        }
