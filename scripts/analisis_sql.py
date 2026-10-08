import argparse
import re
import sqlite3
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "database" / "norton_bisnis.db"
SQL_PATH = BASE_DIR / "sql" / "analisis.sql"
OUTPUT_DIR = BASE_DIR / "outputs"


def read_queries():
    content = SQL_PATH.read_text(encoding="utf-8")
    parts = re.split(r"(?m)^-- query: ([\w-]+)\s*$", content)
    return list(zip(parts[1::2], parts[2::2]))


def run_analysis(db_path=DB_PATH, output_dir=OUTPUT_DIR):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    with sqlite3.connect(db_path) as con:
        for name, sql in read_queries():
            frame = pd.read_sql_query(sql, con)
            frame.to_csv(output_dir / f"{name}.csv", index=False, encoding="utf-8-sig")
            results[name] = frame
    return results


def main():
    parser = argparse.ArgumentParser(description="Jalankan analisis SQL database Norton")
    parser.add_argument("--database", type=Path, default=DB_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    for name, frame in run_analysis(args.database, args.output_dir).items():
        print(f"\n{name}")
        print(frame.to_string(index=False))
    print(f"\nCSV analisis tersimpan di: {args.output_dir}")


if __name__ == "__main__":
    main()
