from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import statistics
from pathlib import Path
from typing import Any

from sparkle.config import data_root
from sparkle.contracts import ToolDefinition
from sparkle.storage import SQLiteStore, utc_now


class DataAnalysisError(ValueError):
    pass


class DataAnalysisService(SQLiteStore):
    """Bounded deterministic datasets plus reproducible analysis artifacts."""

    NAME = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
    FILTERS = {"eq", "ne", "gt", "gte", "lt", "lte", "contains"}
    MATH = {"add", "subtract", "multiply", "divide"}
    AGGREGATES = {"count", "sum", "mean", "min", "max"}
    CHARTS = {"bar", "line", "scatter"}
    MAX_BYTES = 1_000_000
    MAX_ROWS = 5_000
    MAX_COLUMNS = 100
    MAX_CELL = 10_000
    MAX_OPERATIONS = 20
    MAX_OUTPUT_ROWS = 1_000
    MAX_CHART_POINTS = 500

    def __init__(self, path: Path | None = None):
        super().__init__(path or data_root() / "data_environment" / "analysis.sqlite3")
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS data_datasets(
                name TEXT PRIMARY KEY,title TEXT NOT NULL,source_format TEXT NOT NULL,
                source_digest TEXT NOT NULL,columns_json TEXT NOT NULL,rows_json TEXT NOT NULL,
                row_count INTEGER NOT NULL,revision INTEGER NOT NULL,archived INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,updated_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS data_analysis_runs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,dataset_name TEXT NOT NULL,dataset_revision INTEGER NOT NULL,
                recipe_json TEXT NOT NULL,recipe_digest TEXT NOT NULL,result_json TEXT NOT NULL,created_at TEXT NOT NULL,
                FOREIGN KEY(dataset_name) REFERENCES data_datasets(name))""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_data_analysis_runs ON data_analysis_runs(dataset_name,id DESC)")
            db.execute("""CREATE TABLE IF NOT EXISTS data_analysis_events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,dataset_name TEXT NOT NULL,event TEXT NOT NULL,
                revision INTEGER NOT NULL,operator TEXT NOT NULL,created_at TEXT NOT NULL)""")

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

    @classmethod
    def _digest(cls, value: Any) -> str:
        return hashlib.sha256(cls._json(value).encode()).hexdigest()

    @classmethod
    def _name(cls, value: str) -> str:
        if not isinstance(value, str) or not cls.NAME.fullmatch(value):
            raise DataAnalysisError("Dataset name must be a 2-64 character lowercase identifier")
        return value

    @classmethod
    def _column(cls, value: Any) -> str:
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > 128 or any(ord(c) < 32 for c in value):
            raise DataAnalysisError("Column names must contain 1-128 printable characters")
        return value.strip()

    @classmethod
    def _scalar(cls, value: Any) -> Any:
        if value is None or type(value) in {bool, int}:
            return value
        if type(value) is float:
            if math.isfinite(value): return value
            raise DataAnalysisError("Numeric values must be finite")
        if isinstance(value, str) and len(value) <= cls.MAX_CELL:
            return value
        raise DataAnalysisError("Dataset cells must be bounded scalar JSON values")

    @classmethod
    def _infer_csv(cls, values: list[Any]) -> list[Any]:
        present = [v for v in values if v not in {None, ""}]
        if not present: return [None] * len(values)
        if all(isinstance(v, str) and v.lower() in {"true", "false"} for v in present):
            return [None if v in {None, ""} else str(v).lower() == "true" for v in values]
        integer = re.compile(r"^[+-]?(?:0|[1-9]\d*)$")
        if all(isinstance(v, str) and integer.fullmatch(v) for v in present):
            return [None if v in {None, ""} else int(v) for v in values]
        try:
            numbers = [float(v) for v in present]
            if all(math.isfinite(v) for v in numbers):
                it = iter(numbers)
                return [None if v in {None, ""} else next(it) for v in values]
        except (TypeError, ValueError):
            pass
        return [None if v in {None, ""} else str(v) for v in values]

    @classmethod
    def _parse(cls, fmt: str, content: str) -> tuple[list[str], list[dict[str, Any]]]:
        if fmt not in {"csv", "json"}: raise DataAnalysisError("Data format must be csv or json")
        if not isinstance(content, str) or not content.strip(): raise DataAnalysisError("Dataset content is empty")
        if len(content.encode()) > cls.MAX_BYTES: raise DataAnalysisError("Dataset source exceeds the 1 MB limit")
        if fmt == "csv":
            try:
                reader = csv.DictReader(io.StringIO(content, newline=""))
                if reader.fieldnames is None: raise DataAnalysisError("CSV must contain a header row")
                columns = [cls._column(v) for v in reader.fieldnames]
                raw = [dict(row) for row in reader]
                inferred = {c: cls._infer_csv([row.get(c) for row in raw]) for c in columns}
                rows = [{c: inferred[c][i] for c in columns} for i in range(len(raw))]
            except csv.Error as exc:
                raise DataAnalysisError("CSV parsing failed") from exc
        else:
            try: raw = json.loads(content)
            except json.JSONDecodeError as exc: raise DataAnalysisError("JSON parsing failed") from exc
            if not isinstance(raw, list) or not raw or not all(isinstance(row, dict) for row in raw):
                raise DataAnalysisError("JSON datasets must be a non-empty array of objects")
            columns, seen = [], set()
            for row in raw:
                for key in row:
                    key = cls._column(key)
                    if key not in seen: seen.add(key); columns.append(key)
            rows = [{c: row.get(c) for c in columns} for row in raw]
        if not columns or len(columns) > cls.MAX_COLUMNS or len(columns) != len(set(columns)):
            raise DataAnalysisError("Dataset requires 1-100 unique columns")
        if not rows or len(rows) > cls.MAX_ROWS: raise DataAnalysisError("Dataset requires 1-5000 rows")
        return columns, [{c: cls._scalar(row.get(c)) for c in columns} for row in rows]

    def ingest(self, name: str, content: str, *, source_format: str, title: str | None = None,
               expected_revision: int = 0, operator: str = "operator") -> dict[str, Any]:
        name = self._name(name)
        if type(expected_revision) is not int or expected_revision < 0: raise DataAnalysisError("Invalid expected revision")
        if not isinstance(operator, str) or not operator.strip() or len(operator) > 80: raise DataAnalysisError("Operator identity is required")
        title = title.strip() if isinstance(title, str) and title.strip() else name.replace("_", " ").title()
        if len(title) > 200: raise DataAnalysisError("Dataset title exceeds 200 characters")
        columns, rows = self._parse(source_format, content)
        digest, now = hashlib.sha256(content.encode()).hexdigest(), utc_now()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute("SELECT revision,created_at FROM data_datasets WHERE name=?", (name,)).fetchone()
            actual = int(current["revision"]) if current else 0
            if actual != expected_revision: raise DataAnalysisError(f"Dataset revision conflict: expected {expected_revision}, current {actual}")
            revision, created = actual + 1, current["created_at"] if current else now
            db.execute("""INSERT INTO data_datasets VALUES(?,?,?,?,?,?,?,?,0,?,?)
                ON CONFLICT(name) DO UPDATE SET title=excluded.title,source_format=excluded.source_format,
                source_digest=excluded.source_digest,columns_json=excluded.columns_json,rows_json=excluded.rows_json,
                row_count=excluded.row_count,revision=excluded.revision,archived=0,updated_at=excluded.updated_at""",
                (name,title,source_format,digest,self._json(columns),self._json(rows),len(rows),revision,created,now))
            db.execute("INSERT INTO data_analysis_events(dataset_name,event,revision,operator,created_at) VALUES(?,?,?,?,?)",
                       (name,"ingest",revision,operator.strip(),now))
        return self.inspect(name)

    def datasets(self, *, include_archived: bool = False) -> list[dict[str, Any]]:
        query = "SELECT name,title,source_format,source_digest,row_count,revision,archived,created_at,updated_at FROM data_datasets"
        if not include_archived: query += " WHERE archived=0"
        with self.connect() as db: rows = db.execute(query + " ORDER BY name").fetchall()
        return [dict(row) | {"archived": bool(row["archived"])} for row in rows]

    def inspect(self, name: str, *, sample: int = 20, include_archived: bool = False) -> dict[str, Any]:
        name = self._name(name)
        if type(sample) is not int or not 0 <= sample <= 100: raise DataAnalysisError("Sample size must be 0-100")
        with self.connect() as db: row = db.execute("SELECT * FROM data_datasets WHERE name=?", (name,)).fetchone()
        if row is None or (row["archived"] and not include_archived): raise DataAnalysisError("Unknown active dataset")
        return {"name":row["name"],"title":row["title"],"source_format":row["source_format"],
                "source_digest":row["source_digest"],"columns":json.loads(row["columns_json"]),"row_count":row["row_count"],
                "revision":row["revision"],"archived":bool(row["archived"]),"created_at":row["created_at"],"updated_at":row["updated_at"],
                "sample":json.loads(row["rows_json"])[:sample]}

    def archive(self, name: str, *, expected_revision: int, operator: str = "operator") -> dict[str, Any]:
        name = self._name(name)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT revision,archived FROM data_datasets WHERE name=?", (name,)).fetchone()
            if row is None: raise DataAnalysisError("Unknown dataset")
            if int(row["revision"]) != expected_revision: raise DataAnalysisError(f"Dataset revision conflict: expected {expected_revision}, current {row['revision']}")
            if row["archived"]: raise DataAnalysisError("Dataset is already archived")
            revision, now = expected_revision + 1, utc_now()
            db.execute("UPDATE data_datasets SET archived=1,revision=?,updated_at=? WHERE name=?", (revision,now,name))
            db.execute("INSERT INTO data_analysis_events(dataset_name,event,revision,operator,created_at) VALUES(?,?,?,?,?)",
                       (name,"archive",revision,operator,now))
        return self.inspect(name, include_archived=True)

    def _load(self, name: str) -> tuple[dict[str, Any], list[str], list[dict[str, Any]]]:
        name = self._name(name)
        with self.connect() as db: row = db.execute("SELECT * FROM data_datasets WHERE name=? AND archived=0", (name,)).fetchone()
        if row is None: raise DataAnalysisError("Unknown active dataset")
        return dict(row), json.loads(row["columns_json"]), json.loads(row["rows_json"])

    @staticmethod
    def _number(value: Any) -> float | int:
        if type(value) not in {int, float} or not math.isfinite(float(value)): raise DataAnalysisError("Operation requires finite numeric values")
        return value

    @classmethod
    def _summary(cls, columns: list[str], rows: list[dict[str, Any]]) -> dict[str, Any]:
        result = {}
        for column in columns:
            values = [row.get(column) for row in rows]
            present = [v for v in values if v not in {None, ""}]
            numeric = [float(v) for v in present if type(v) in {int, float} and math.isfinite(float(v))]
            item = {"count":len(present),"missing":len(values)-len(present),"unique":len({cls._json(v) for v in present})}
            if numeric: item["numeric"] = {"count":len(numeric),"min":min(numeric),"max":max(numeric),"sum":sum(numeric),"mean":statistics.fmean(numeric),"median":statistics.median(numeric)}
            result[column] = item
        return result

    @classmethod
    def _group(cls, rows: list[dict[str, Any]], columns: list[str], spec: Any) -> list[dict[str, Any]] | None:
        if spec is None: return None
        if not isinstance(spec, dict) or set(spec) != {"by","metrics"}: raise DataAnalysisError("Invalid group specification")
        by, metrics = spec["by"], spec["metrics"]
        if not isinstance(by,list) or not 1 <= len(by) <= 5 or any(c not in columns for c in by): raise DataAnalysisError("Invalid group columns")
        if not isinstance(metrics,list) or not 1 <= len(metrics) <= 20: raise DataAnalysisError("Invalid group metrics")
        parsed, outputs = [], set(by)
        for metric in metrics:
            if not isinstance(metric,dict) or set(metric)-{"column","op","as"}: raise DataAnalysisError("Invalid group metric")
            column, op = metric.get("column"), metric.get("op")
            output = cls._column(metric.get("as") or f"{op}_{column}")
            if column not in columns or op not in cls.AGGREGATES or output in outputs: raise DataAnalysisError("Invalid group metric")
            outputs.add(output); parsed.append((column,op,output))
        groups: dict[tuple[Any,...],list[dict[str,Any]]] = {}
        for row in rows: groups.setdefault(tuple(row.get(c) for c in by),[]).append(row)
        out = []
        for key,members in sorted(groups.items(),key=lambda item:cls._json(item[0])):
            record = dict(zip(by,key,strict=True))
            for column,op,output in parsed:
                values = [m.get(column) for m in members if m.get(column) not in {None,""}]
                if op == "count": record[output] = len(values); continue
                nums = [float(cls._number(v)) for v in values]
                record[output] = None if not nums else ({"sum":sum,"mean":statistics.fmean,"min":min,"max":max}[op])(nums)
            out.append(record)
            if len(out) > cls.MAX_OUTPUT_ROWS: raise DataAnalysisError("Grouped result exceeds output limit")
        return out

    def analyze(self, name: str, recipe: dict[str, Any], *, persist: bool = True, operator: str = "operator") -> dict[str, Any]:
        dataset, columns, rows = self._load(name)
        if not isinstance(recipe,dict) or set(recipe)-{"operations","group","chart","include_rows"}: raise DataAnalysisError("Unsupported analysis recipe fields")
        operations = recipe.get("operations",[])
        if not isinstance(operations,list) or len(operations) > self.MAX_OPERATIONS: raise DataAnalysisError("Too many analysis operations")
        work_columns, work_rows = list(columns), [dict(row) for row in rows]
        for item in operations:
            if not isinstance(item,dict) or "op" not in item: raise DataAnalysisError("Each operation requires op")
            op = item["op"]
            if op == "filter":
                if set(item)-{"op","column","operator","value"}: raise DataAnalysisError("Invalid filter")
                column, compare, expected = item.get("column"), item.get("operator"), self._scalar(item.get("value"))
                if column not in work_columns or compare not in self.FILTERS: raise DataAnalysisError("Invalid filter")
                def keep(row):
                    actual=row.get(column)
                    if compare=="eq": return actual==expected
                    if compare=="ne": return actual!=expected
                    if compare=="contains": return isinstance(actual,str) and str(expected) in actual
                    if actual is None or expected is None: return False
                    try: return {"gt":actual>expected,"gte":actual>=expected,"lt":actual<expected,"lte":actual<=expected}[compare]
                    except TypeError as exc: raise DataAnalysisError("Filter values are not comparable") from exc
                work_rows=[row for row in work_rows if keep(row)]
            elif op == "select":
                selected=item.get("columns")
                if set(item)!={"op","columns"} or not isinstance(selected,list) or not selected or len(selected)!=len(set(selected)) or any(c not in work_columns for c in selected): raise DataAnalysisError("Invalid select")
                work_columns=list(selected); work_rows=[{c:row.get(c) for c in work_columns} for row in work_rows]
            elif op == "sort":
                if set(item)-{"op","column","descending"} or item.get("column") not in work_columns or type(item.get("descending",False)) is not bool: raise DataAnalysisError("Invalid sort")
                column=item["column"]; work_rows=sorted(work_rows,key=lambda r:(r.get(column) is None,self._json(r.get(column))),reverse=item.get("descending",False))
            elif op == "limit":
                if set(item)!={"op","count"} or type(item.get("count")) is not int or not 0 <= item["count"] <= self.MAX_OUTPUT_ROWS: raise DataAnalysisError("Invalid limit")
                work_rows=work_rows[:item["count"]]
            elif op == "compute":
                if set(item)-{"op","output","left","operator","right_column","right_value"}: raise DataAnalysisError("Invalid compute")
                output,left,math_op=self._column(item.get("output")),item.get("left"),item.get("operator")
                if output in work_columns or left not in work_columns or math_op not in self.MATH: raise DataAnalysisError("Invalid compute")
                has_col,has_val="right_column" in item,"right_value" in item
                if has_col==has_val or (has_col and item["right_column"] not in work_columns): raise DataAnalysisError("Invalid compute operand")
                constant=self._scalar(item.get("right_value")) if has_val else None
                for row in work_rows:
                    a=self._number(row.get(left)); b=self._number(row.get(item.get("right_column"))) if has_col else self._number(constant)
                    if math_op=="add": value=a+b
                    elif math_op=="subtract": value=a-b
                    elif math_op=="multiply": value=a*b
                    else:
                        if b==0: raise DataAnalysisError("Compute division by zero")
                        value=a/b
                    if not math.isfinite(float(value)): raise DataAnalysisError("Computed value is not finite")
                    row[output]=value
                work_columns.append(output)
            else: raise DataAnalysisError("Unsupported analysis operation")
        include_rows=recipe.get("include_rows",True)
        if type(include_rows) is not bool: raise DataAnalysisError("include_rows must be boolean")
        if include_rows and len(work_rows)>self.MAX_OUTPUT_ROWS: raise DataAnalysisError("Result exceeds 1000 rows; add limit or disable include_rows")
        chart=None
        if recipe.get("chart") is not None:
            spec=recipe["chart"]
            if not isinstance(spec,dict) or set(spec)!={"kind","x","y"} or spec["kind"] not in self.CHARTS or spec["x"] not in work_columns or spec["y"] not in work_columns: raise DataAnalysisError("Invalid chart specification")
            points=[{"x":row.get(spec["x"]),"y":row.get(spec["y"])} for row in work_rows[:self.MAX_CHART_POINTS]]
            chart=spec|{"points":points,"truncated":len(points)<len(work_rows)}
        normalized=json.loads(self._json(recipe))
        result={"dataset":{"name":name,"revision":dataset["revision"],"source_digest":dataset["source_digest"]},"recipe":normalized,
                "recipe_digest":self._digest(normalized),"columns":work_columns,"row_count":len(work_rows),"summary":self._summary(work_columns,work_rows),
                "group":self._group(work_rows,work_columns,recipe.get("group")),"chart":chart,"rows":work_rows if include_rows else None}
        if persist:
            now=utc_now()
            with self.connect() as db:
                cur=db.execute("INSERT INTO data_analysis_runs(dataset_name,dataset_revision,recipe_json,recipe_digest,result_json,created_at) VALUES(?,?,?,?,?,?)",
                               (name,dataset["revision"],self._json(normalized),result["recipe_digest"],self._json(result),now))
                result=result|{"analysis_id":int(cur.lastrowid),"created_at":now}
        return result

    def history(self, name: str, *, limit: int = 20) -> list[dict[str, Any]]:
        name=self._name(name)
        if type(limit) is not int or not 1<=limit<=100: raise DataAnalysisError("History limit must be 1-100")
        with self.connect() as db: rows=db.execute("SELECT id,dataset_revision,recipe_digest,recipe_json,created_at FROM data_analysis_runs WHERE dataset_name=? ORDER BY id DESC LIMIT ?",(name,limit)).fetchall()
        return [dict(row)|{"recipe":json.loads(row["recipe_json"])} for row in rows]

    def stats(self) -> dict[str, Any]:
        with self.connect() as db:
            active=db.execute("SELECT count(*) FROM data_datasets WHERE archived=0").fetchone()[0]
            archived=db.execute("SELECT count(*) FROM data_datasets WHERE archived=1").fetchone()[0]
            runs=db.execute("SELECT count(*) FROM data_analysis_runs").fetchone()[0]
        return {"status":"ready","datasets":active,"archived_datasets":archived,"analysis_runs":runs}


class DataAnalysisTool:
    name="data_analyze"
    description="Run a bounded deterministic recipe against an operator-imported dataset without mutating stored data."
    parameters={"type":"object","properties":{"dataset":{"type":"string"},"recipe":{"type":"object"}},"required":["dataset","recipe"],"additionalProperties":False}

    def __init__(self, service: DataAnalysisService): self.service=service
    def definition(self) -> ToolDefinition: return ToolDefinition(self.name,self.description,self.parameters)
    def run(self, arguments: dict[str, Any]) -> Any:
        if not isinstance(arguments,dict) or set(arguments)!={"dataset","recipe"} or not isinstance(arguments.get("recipe"),dict): raise DataAnalysisError("Dataset and recipe are required")
        return self.service.analyze(str(arguments["dataset"]),arguments["recipe"],persist=False,operator="model_tool")
