"""
run_analysis.py — Asset Hub ID Analysis
=========================================
Entry point. Orchestrates loading, analysis, charting, and summary.

Usage
-----
    python run.py

Outputs (written to outputs/)
-----------------------------
    outputs/schema.md                — Database schema documentation
    outputs/graphic1_taxonomy.png    — Five-bucket severity taxonomy     (mail 1)
    outputs/property_graph.md        — Property graph as structured markdown (mail 3)
    outputs/graphic3_resolution.png  — Resolution rate + donut summary    (mail 2)
    outputs/analysis_summary.md     — LLM-generated narrative report

Other artefacts
---------------
    assethub.duckdb              — Persistent DuckDB database (relational model)

Module layout
-------------
    ah_loader.py            Configuration + DuckDB persistent schema + import
    ah_analysis.py          DuckDB SQL queries + summary writer
    ah_narrative.py         LLM narrative generation
    ah_plot_taxonomy.py     Graphic 1 — five-bucket taxonomy
    ah_graph_md.py          Property graph as markdown
    ah_plot_resolution.py   Graphic 3 — resolution rate bar + donut
    run.py                  This file — entry point only

Dependencies
------------
    pip install pandas matplotlib openpyxl duckdb anthropic python-dotenv

Environment variables
---------------------
    ANTHROPIC_API_KEY   — required for LLM narrative (falls back to structured report)
"""

from ah_loader          import get_connection, get_previous_run, INPUT_FILE
from ah_analysis        import run_analysis, write_summary
from ah_plot_taxonomy   import plot_taxonomy
from ah_graph_md        import write_property_graph_md
from ah_plot_resolution import plot_resolution


def write_schema(con, out_path: str):
    """Export the DuckDB schema as a markdown document."""
    lines = [
        '# Asset Hub — Database Schema',
        '',
        'Persistent DuckDB database (`assethub.duckdb`).',
        'Each Excel import creates a new run; all history is retained.',
        '',
    ]

    # Get all tables
    tables = con.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'main'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """).fetchall()

    for (table_name,) in tables:
        lines += [f'## Table: `{table_name}`', '']

        cols = con.execute(f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = '{table_name}'
              AND table_schema = 'main'
            ORDER BY ordinal_position
        """).fetchall()

        lines += [
            '| Column | Type | Nullable |',
            '|--------|------|----------|',
        ]
        for col_name, dtype, nullable in cols:
            lines.append(f'| {col_name} | {dtype} | {nullable} |')

        row_count = con.execute(
            f"SELECT COUNT(*) FROM {table_name}"
        ).fetchone()[0]
        lines += ['', f'Rows: {row_count}', '']

    # Get all views
    views = con.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'main'
          AND table_type = 'VIEW'
        ORDER BY table_name
    """).fetchall()

    if views:
        for (view_name,) in views:
            lines += [f'## View: `{view_name}`', '']

            cols = con.execute(f"""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = '{view_name}'
                  AND table_schema = 'main'
                ORDER BY ordinal_position
            """).fetchall()

            lines += [
                '| Column | Type | Nullable |',
                '|--------|------|----------|',
            ]
            for col_name, dtype, nullable in cols:
                lines.append(f'| {col_name} | {dtype} | {nullable} |')
            lines.append('')

    # Run history
    runs = con.execute(
        "SELECT run_id, timestamp, source_file FROM runs ORDER BY run_id"
    ).fetchall()
    if runs:
        lines += [
            '## Run History',
            '',
            '| Run | Timestamp | Source File |',
            '|-----|-----------|-------------|',
        ]
        for run_id, ts, src in runs:
            lines.append(f'| {run_id} | {ts} | {src} |')
        lines.append('')

    with open(out_path, 'w') as f:
        f.write('\n'.join(lines))
    print(f"  ✓  {out_path}")


def main():
    print(f"\nLoading {INPUT_FILE} …")
    con = get_connection(INPUT_FILE)

    previous = get_previous_run(con)
    if previous:
        print(f"  Previous run: #{previous['run_id']} ({previous['timestamp']})")

    print("Running analysis …")
    results = run_analysis(con)

    print("Generating outputs …")
    out = "outputs"
    write_schema(con,                f"{out}/schema.md")
    plot_taxonomy(results,           f"{out}/graphic1_taxonomy.png")
    write_property_graph_md(results, f"{out}/property_graph.md")
    plot_resolution(results,         f"{out}/graphic3_resolution.png")
    write_summary(results,           f"{out}/analysis_summary.md", previous=previous)

    print(f"\nDone. All files written to {out}/.")


if __name__ == '__main__':
    main()
