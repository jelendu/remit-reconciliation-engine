"""Load the generated Parquet files into DuckDB (warehouse/raw.duckdb, schema `raw`).

Full reload each run — the generator owns history (it appends batches to its
output files), so reloading is idempotent and keeps loader logic trivial.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

WAREHOUSE = Path(__file__).resolve().parent / "raw.duckdb"
DATA_DIR = Path(__file__).resolve().parent.parent / "data_gen" / "output"

RAW_TABLES = ["accounts", "payments", "remits", "utility_charges",
              "cust_charges", "adjustment_amts", "adjustments", "export_rc"]


def main() -> None:
    con = duckdb.connect(str(WAREHOUSE))
    # the catalog is also named `raw` (from raw.duckdb), so qualify fully
    con.execute("CREATE SCHEMA IF NOT EXISTS raw.raw")
    for table in RAW_TABLES:
        parquet = DATA_DIR / f"{table}.parquet"
        if not parquet.exists():
            raise FileNotFoundError(f"{parquet} — run data_gen/generate.py first")
        con.execute(f"""
            CREATE OR REPLACE TABLE raw.raw.{table} AS
            SELECT * FROM read_parquet('{parquet.as_posix()}')
        """)

    print(f"=== loaded into {WAREHOUSE} ===")
    rows = con.execute("""
        SELECT table_name, estimated_size AS row_count
        FROM duckdb_tables()
        WHERE schema_name = 'raw'
        ORDER BY table_name
    """).fetchall()
    for name, count in rows:
        print(f"  raw.{name:<18} {count:>6} rows")
    con.close()


if __name__ == "__main__":
    main()
