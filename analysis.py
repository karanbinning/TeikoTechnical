import os
import sqlite3

import pandas as pd
from scipy.stats import mannwhitneyu

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "clinical_trial.db")

POPULATIONS = ["b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte"]


def _get_connection() -> sqlite3.Connection:
    """Return an open connection to clinical_trial.db."""
    return sqlite3.connect(DB_PATH)


def get_frequency_table() -> pd.DataFrame:
    """Return per-sample counts, totals, and population percentages."""
    query = """
        SELECT cc.sample, cc.population, cc.count
        FROM cell_counts cc
        JOIN samples s ON cc.sample = s.sample
        ORDER BY cc.sample, cc.population
    """
    conn = _get_connection()
    try:
        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()

    totals = df.groupby("sample")["count"].sum().rename("total_count")
    df = df.merge(totals, on="sample")
    df["percentage"] = (df["count"] / df["total_count"] * 100).round(2)
    df["population"] = df["population"].astype(
        pd.CategoricalDtype(categories=POPULATIONS, ordered=True)
    )
    return df.sort_values(["sample", "population"]).reset_index(drop=True)


def get_responder_stats() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return plot data and Mann-Whitney stats for miraclib melanoma PBMC samples."""
    freq = get_frequency_table()
    conn = _get_connection()
    try:
        meta = pd.read_sql_query(
            """
            SELECT s.sample, sub.response
            FROM samples s
            JOIN subjects sub ON s.subject = sub.subject
            WHERE sub.condition = 'melanoma'
              AND s.treatment = 'miraclib'
              AND s.sample_type = 'PBMC'
            """,
            conn,
        )
    finally:
        conn.close()

    plot_df = freq.merge(meta, on="sample")[["sample", "population", "percentage", "response"]]

    stats_rows = []
    for population in POPULATIONS:
        pop = plot_df[plot_df["population"] == population]
        yes_pct = pop.loc[pop["response"] == "yes", "percentage"]
        no_pct = pop.loc[pop["response"] == "no", "percentage"]

        if len(yes_pct) > 0 and len(no_pct) > 0:
            _, p_value = mannwhitneyu(yes_pct, no_pct, alternative="two-sided")
        else:
            p_value = float("nan")

        stats_rows.append(
            {
                "population": population,
                "p_value": round(p_value, 4) if pd.notna(p_value) else p_value,
                "significant": p_value < 0.05 if pd.notna(p_value) else False,
                "median_responders": yes_pct.median() if len(yes_pct) > 0 else None,
                "median_non_responders": no_pct.median() if len(no_pct) > 0 else None,
            }
        )

    return plot_df, pd.DataFrame(stats_rows)


def get_baseline_subset() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return baseline miraclib melanoma PBMC summary tables."""
    query = """
        SELECT sub.project, s.subject, sub.response, sub.sex
        FROM samples s
        JOIN subjects sub ON s.subject = sub.subject
        WHERE sub.condition = 'melanoma'
          AND s.sample_type = 'PBMC'
          AND s.time_from_treatment_start = 0
          AND s.treatment = 'miraclib'
    """
    conn = _get_connection()
    try:
        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()

    samples_per_project = (
        df.groupby("project", as_index=False).size().rename(columns={"size": "sample_count"})
    )
    response_counts = df.groupby("response")["subject"].nunique().reset_index(name="subject_count")
    sex_counts = df.groupby("sex")["subject"].nunique().reset_index(name="subject_count")
    return samples_per_project, response_counts, sex_counts
