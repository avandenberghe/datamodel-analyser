"""
ah_loader.py — Asset Hub ID Analysis
=====================================
Persistent DuckDB database with relational schema.

Flow:
  1. Excel is read once and normalised into relational tables inside
     assethub.duckdb (concepts, relationships, raw_rows).
  2. Each import is a timestamped run — previous runs stay in the DB.
  3. A view  v  provides backwards-compatible access for all analysis
     queries (same column names as before).
  4. All downstream modules query the persistent DB, not the Excel.

Expected column names in the workbook
--------------------------------------
    concept_name, system_of_record, source_table, id_mapping,
    identifier_mapped, identifier_mapping, id_unique, identifier_unique,
    related_concept, relationship_type, related_id_mapping,
    related_identifier_mapped, related_identifier_mapping,
    rel_guid_in_source, rel_guid_fetched, comment
"""

import pandas as pd
import duckdb
from datetime import datetime, timezone

# ── Configuration ─────────────────────────────────────────────────────────────

INPUT_FILE = "input/excel.xlsx"
DB_FILE    = "assethub.duckdb"
DPI        = 180     # output resolution for all PNG graphics


# ── Schema DDL ───────────────────────────────────────────────────────────────

_SCHEMA_DDL = """
-- Import runs
CREATE TABLE IF NOT EXISTS runs (
    run_id      INTEGER PRIMARY KEY,
    timestamp   TIMESTAMP NOT NULL,
    source_file VARCHAR NOT NULL
);

CREATE SEQUENCE IF NOT EXISTS seq_run_id START 1;

-- One row per concept (deduplicated per run)
CREATE TABLE IF NOT EXISTS concepts (
    run_id              INTEGER NOT NULL REFERENCES runs(run_id),
    concept             VARCHAR NOT NULL,
    sor                 VARCHAR NOT NULL,
    sor_table           VARCHAR,
    id_mapping          VARCHAR,
    identifier_mapped   VARCHAR,     -- 'yes' / 'no' = has GUID
    identifier_mapping  VARCHAR,
    id_unique           VARCHAR,     -- 'yes' / 'no'
    comment             VARCHAR,
    PRIMARY KEY (run_id, concept, sor)
);

-- One row per relationship
CREATE TABLE IF NOT EXISTS relationships (
    run_id              INTEGER NOT NULL REFERENCES runs(run_id),
    concept             VARCHAR NOT NULL,
    sor                 VARCHAR NOT NULL,
    related             VARCHAR NOT NULL,
    rel_type            VARCHAR,     -- 'to one' / 'to many'
    rel_guid_in_source  VARCHAR,
    rel_guid_fetched    VARCHAR,
    comment             VARCHAR
);

-- Raw import rows (full denormalised data, for audit)
CREATE TABLE IF NOT EXISTS raw_rows (
    run_id              INTEGER NOT NULL REFERENCES runs(run_id),
    concept             VARCHAR,
    sor                 VARCHAR,
    sor_table           VARCHAR,
    id_mapping          VARCHAR,
    identifier_mapped   VARCHAR,
    identifier_mapping  VARCHAR,
    id_unique           VARCHAR,
    related             VARCHAR,
    rel_type            VARCHAR,
    rel_guid_in_source  VARCHAR,
    rel_guid_fetched    VARCHAR,
    comment             VARCHAR
);
"""

# ── Normalised view (backwards-compatible with all analysis queries) ─────────

_VIEW_DDL = """
CREATE OR REPLACE VIEW v AS
SELECT
    r.concept,
    r.sor,
    r.sor_table,
    r.id_mapping,
    r.identifier_mapped,
    r.identifier_mapping,
    r.id_unique,
    r.related,
    r.rel_type,
    r.rel_guid_in_source,
    r.rel_guid_fetched,
    r.comment
FROM raw_rows r
WHERE r.run_id = (SELECT MAX(run_id) FROM runs)
  AND r.concept IS NOT NULL
  AND r.concept != ''
"""


# ── Import logic ─────────────────────────────────────────────────────────────

def _normalise(val):
    """Trim and lowercase a string value, return '' for NULL."""
    if pd.isna(val) or val is None:
        return ''
    return str(val).strip().lower()


def _trim(val):
    """Trim a string value, return '' for NULL (no lowercasing)."""
    if pd.isna(val) or val is None:
        return ''
    return str(val).strip()


def _import_excel(con: duckdb.DuckDBPyConnection, path: str) -> int:
    """
    Import an Excel file into the relational schema.
    Returns the run_id of the new import.
    """
    df = pd.read_excel(path, header=0)

    # Create the new run
    ts = datetime.now(timezone.utc)
    run_id = con.execute(
        "SELECT nextval('seq_run_id')"
    ).fetchone()[0]
    con.execute(
        "INSERT INTO runs (run_id, timestamp, source_file) VALUES (?, ?, ?)",
        [run_id, ts, path]
    )

    # Normalise all rows and insert into raw_rows
    rows = []
    for _, row in df.iterrows():
        concept = _trim(row.get('concept_name', ''))
        if not concept:
            continue
        rows.append((
            run_id,
            concept,
            _normalise(row.get('system_of_record', '')),
            _trim(row.get('source_table', '')),
            _trim(row.get('id_mapping', '')),
            _normalise(row.get('identifier_mapped', '')),
            _trim(row.get('identifier_mapping', '')),
            _normalise(row.get('id_unique', '')),
            _trim(row.get('related_concept', '')),
            _normalise(row.get('relationship_type', '')),
            _normalise(row.get('rel_guid_in_source', '')),
            _normalise(row.get('rel_guid_fetched', '')),
            _trim(row.get('comment', '')),
        ))

    con.executemany(
        "INSERT INTO raw_rows VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows
    )

    # Populate deduplicated concepts table (one row per concept+sor,
    # pick the first row's values for columns that may vary across
    # the denormalised raw rows)
    con.execute("""
        INSERT INTO concepts (
            run_id, concept, sor, sor_table, id_mapping,
            identifier_mapped, identifier_mapping, id_unique, comment
        )
        SELECT
            run_id,
            concept,
            sor,
            FIRST(sor_table),
            FIRST(id_mapping),
            FIRST(identifier_mapped),
            FIRST(identifier_mapping),
            FIRST(id_unique),
            FIRST(comment)
        FROM raw_rows
        WHERE run_id = ?
          AND sor != ''
        GROUP BY run_id, concept, sor
    """, [run_id])

    # Populate relationships table
    con.execute("""
        INSERT INTO relationships (
            run_id, concept, sor, related, rel_type,
            rel_guid_in_source, rel_guid_fetched, comment
        )
        SELECT
            run_id, concept, sor, related, rel_type,
            rel_guid_in_source, rel_guid_fetched, comment
        FROM raw_rows
        WHERE run_id = ?
          AND related != ''
          AND related != 'nan'
    """, [run_id])

    return run_id


# ── Public API ────────────────────────────────────────────────────────────────

def get_connection(path: str = INPUT_FILE) -> duckdb.DuckDBPyConnection:
    """
    Open (or create) the persistent DuckDB database, import the Excel
    file as a new run, and return the connection.

    The view  v  always points to the latest run, so all existing
    analysis queries work unchanged.
    """
    con = duckdb.connect(DB_FILE)
    con.execute(_SCHEMA_DDL)

    run_id = _import_excel(con, path)
    con.execute(_VIEW_DDL)

    run_count = con.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    print(f"  Import complete — run #{run_id} ({run_count} total runs in DB)")

    return con


def get_previous_run(con: duckdb.DuckDBPyConnection) -> dict | None:
    """
    Load the second-most-recent run's metadata and analysis results.
    Temporarily switches the view to the previous run, runs the full
    analysis, then switches back.
    Returns None if there is only one run.
    """
    rows = con.execute("""
        SELECT run_id, timestamp, source_file
        FROM runs
        ORDER BY run_id DESC
        LIMIT 2
    """).fetchall()

    if len(rows) < 2:
        return None

    current_id = rows[0][0]
    prev_id, prev_ts, prev_file = rows[1]

    # Temporarily point view v at the previous run
    con.execute(f"""
        CREATE OR REPLACE VIEW v AS
        SELECT concept, sor, sor_table, id_mapping,
               identifier_mapped, identifier_mapping, id_unique,
               related, rel_type, rel_guid_in_source,
               rel_guid_fetched, comment
        FROM raw_rows
        WHERE run_id = {prev_id}
          AND concept IS NOT NULL AND concept != ''
    """)

    # Run analysis against previous data
    from ah_analysis import run_analysis
    prev_results = run_analysis(con)

    # Restore view to current run
    con.execute(_VIEW_DDL)

    return {
        'run_id': prev_id,
        'timestamp': str(prev_ts),
        'source_file': prev_file,
        'results': prev_results,
    }


def delete_run(con: duckdb.DuckDBPyConnection, run_id: int):
    """
    Delete a run and all its data from the database.
    Refuses to delete the only remaining run.
    """
    # Check the run exists
    exists = con.execute(
        "SELECT COUNT(*) FROM runs WHERE run_id = ?", [run_id]
    ).fetchone()[0]
    if not exists:
        raise ValueError(f"Run #{run_id} does not exist.")

    # Refuse to delete the last run
    total = con.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    if total <= 1:
        raise ValueError("Cannot delete the only remaining run.")

    # Delete in child-first order (FK dependencies)
    for table in ('raw_rows', 'relationships', 'concepts', 'runs'):
        con.execute(f"DELETE FROM {table} WHERE run_id = ?", [run_id])

    # Refresh view to point at the new latest run
    con.execute(_VIEW_DDL)

    remaining = con.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    print(f"  Deleted run #{run_id} ({remaining} runs remaining)")
