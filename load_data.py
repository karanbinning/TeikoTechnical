import os
import sqlite3

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(BASE_DIR, "cell-count.csv")
DB_PATH = os.path.join(BASE_DIR, "clinical_trial.db")

CELL_COLUMNS = ["b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte"]


def load_data() -> None:
    """Load cell-count.csv into clinical_trial.db (drop and recreate tables)."""
    try:
        df = pd.read_csv(CSV_FILE, sep="\t")
        if df.shape[1] == 1:
            df = pd.read_csv(CSV_FILE, sep=",")
    except Exception:
        df = pd.read_csv(CSV_FILE, sep=",")

    df.columns = df.columns.str.strip()
    for col in CELL_COLUMNS:
        df[col] = df[col].fillna(0).astype(int)

    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute("DROP TABLE IF EXISTS cell_counts")
    cursor.execute("DROP TABLE IF EXISTS samples")
    cursor.execute("DROP TABLE IF EXISTS subjects")

    cursor.execute("""
        CREATE TABLE subjects (
            subject   TEXT PRIMARY KEY,
            project   TEXT,
            condition TEXT,
            age       INTEGER,
            sex       TEXT,
            response  TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE samples (
            sample                    TEXT PRIMARY KEY,
            subject                   TEXT,
            treatment                 TEXT,
            sample_type               TEXT,
            time_from_treatment_start INTEGER,
            FOREIGN KEY (subject) REFERENCES subjects (subject)
        )
    """)

    cursor.execute("""
        CREATE TABLE cell_counts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            sample     TEXT,
            population TEXT,
            count      INTEGER,
            FOREIGN KEY (sample) REFERENCES samples (sample)
        )
    """)

    df[["subject", "project", "condition", "age", "sex", "response"]].drop_duplicates().to_sql(
        "subjects", connection, if_exists="append", index=False
    )
    df[["sample", "subject", "treatment", "sample_type", "time_from_treatment_start"]].to_sql(
        "samples", connection, if_exists="append", index=False
    )
    df.melt(
        id_vars=["sample"],
        value_vars=CELL_COLUMNS,
        var_name="population",
        value_name="count",
    ).to_sql("cell_counts", connection, if_exists="append", index=False)

    connection.commit()
    connection.close()


if __name__ == "__main__":
    load_data()
