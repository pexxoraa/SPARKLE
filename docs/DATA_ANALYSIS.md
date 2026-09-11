# Data analysis workflows

SPARKLE provides a bounded deterministic data-analysis subsystem for operator-imported CSV and JSON datasets. The implementation is provider-independent and uses the Python standard library plus SQLite. It does not require a model call to ingest, transform, summarize, group, chart, or reproduce an analysis.

## Runtime integration

`SparkleSystem` owns one `DataAnalysisService` at `data_environment/analysis.sqlite3`, exposes subsystem statistics through system status, and registers the read-only `data_analyze` tool. The built-in `data_analysis` agent is the only built-in specialist granted that tool; it may analyze already imported datasets but cannot import, replace, archive, or persist analysis runs through model tool use.

Operator-owned mutation remains outside the model tool boundary through the dedicated `sparkle-data` CLI. Data state follows the normal `SPARKLE_DATA_DIR` architecture and therefore remains independent of the repository checkout.

## Operator workflow

Use the dedicated `sparkle-data` command surface:

- `sparkle-data ingest NAME PATH --approve` imports CSV/JSON data.
- `sparkle-data list` lists active datasets.
- `sparkle-data inspect NAME` shows schema, source digest, revision and bounded sample rows.
- `sparkle-data analyze NAME RECIPE.json --approve` runs and persists a deterministic analysis recipe.
- `sparkle-data history NAME` lists recipe digests and dataset revisions for reproducibility.
- `sparkle-data archive NAME --expected-revision N --approve` archives a dataset using optimistic revision control.

CSV ingestion performs deterministic whole-column inference for booleans, integers and finite floating-point values. Header whitespace is normalized while preserving the corresponding values; collisions after normalization fail closed. JSON datasets must be non-empty arrays of objects containing only bounded scalar JSON values, and duplicate normalized keys fail closed. Missing values are represented as null.

## Analysis recipes

Recipes are JSON objects. Supported row operations are:

- `filter`: `column`, `operator`, `value`; operators are `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `contains`.
- `select`: explicit unique `columns`.
- `sort`: `column` and optional boolean `descending`.
- `limit`: bounded output row count.
- `compute`: arithmetic `add`, `subtract`, `multiply`, or `divide` using a left column and either a right column or constant, producing a new column.

Equality does not alias JSON booleans to numbers. Ordered comparisons accept numeric-to-numeric or string-to-string values only; incompatible types fail closed instead of relying on Python coercion behavior. `contains` is string-only. Numeric sorting uses numeric order rather than serialized lexical order.

Every analysis also computes deterministic per-column count, missing, unique and numeric summary statistics when applicable. Optional grouping supports one to five key columns and `count`, `sum`, `mean`, `min`, and `max` metrics. Optional chart output produces a bounded data specification for `bar`, `line`, or `scatter`; it does not claim that a browser or plotting backend rendered an image.

Persisted analysis records bind the dataset revision, source digest, normalized recipe, recipe SHA-256 digest and deterministic result. Model-facing analysis is read-only and does not create persisted analysis-history records.

## Safety and limits

The subsystem accepts at most 1 MB of source text, 5,000 rows, 100 columns, 10,000 characters per string cell, 20 transform operations, 1,000 returned rows and 500 chart points. Numeric operations reject non-finite values and division by zero. Archive and replacement use revision checks. Dataset source is application data and should be protected with the same storage/back-up controls as other SPARKLE state.

This implementation establishes software-side deterministic analysis, runtime integration and reproducibility. It does not establish statistical validity for arbitrary analyses, causal inference, visualization quality, spreadsheet fidelity, external database connectivity, or real-world analyst correctness. Those remain manual or future connector acceptance concerns, not missing deterministic core behavior.
