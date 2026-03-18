"""
ah_analysis.py — Asset Hub ID Analysis
=========================================
All computation logic expressed as DuckDB SQL queries.
Each query maps directly to a finding or category in the architecture mails.

Every public function receives a DuckDB connection (from ah_loader.get_connection)
and returns either a scalar dict or a DataFrame — never raw SQL strings.
The summary writer is also here since it depends on the results dict.
"""

import duckdb
from ah_loader import INPUT_FILE


# ── SQL query definitions ─────────────────────────────────────────────────────
# Keeping queries as named constants makes them easy to inspect, test, and
# reference by name when explaining methodology to stakeholders.

# Finding 1: GUID availability is a near-perfect predictor of source system.
SQL_GUID_BY_SOR = """
    SELECT sor,
           COUNT(DISTINCT concept)                                              AS total,
           COUNT(DISTINCT CASE WHEN identifier_mapped = 'yes' THEN concept END) AS guid_yes,
           COUNT(DISTINCT CASE WHEN identifier_mapped = 'no'  THEN concept END) AS guid_no,
           ROUND(
               COUNT(DISTINCT CASE WHEN identifier_mapped = 'yes' THEN concept END)
               * 100.0 / COUNT(DISTINCT concept), 1
           )                                                                    AS guid_pct
    FROM v
    WHERE sor != ''
    GROUP BY sor
    ORDER BY sor
"""

# Category A: Non-unique keys — contract violation for a key-value store.
SQL_NON_UNIQUE = """
    SELECT DISTINCT concept, sor, sor_table
    FROM v
    WHERE id_unique = 'no'
    ORDER BY sor, concept
"""

# Category B: Dual-source mastery ambiguity — same concept under multiple SoRs.
SQL_DUAL_SOURCE = """
    SELECT concept,
           COUNT(DISTINCT sor)                      AS sor_count,
           STRING_AGG(DISTINCT sor, ' / ')          AS systems
    FROM v
    WHERE sor != ''
    GROUP BY concept
    HAVING COUNT(DISTINCT sor) > 1
"""

# Category C: No stable cross-system identifier.
# Trangis: structural (Oracle VIEW_*, non-alterable, in decom).
# InfraRef: 3 exceptions (FaultAnalysis, FunctionalSite, FunctionalStation).
SQL_NO_GUID = """
    SELECT sor,
           COUNT(DISTINCT concept)                                              AS count,
           STRING_AGG(DISTINCT concept, ', ' ORDER BY concept)                 AS concepts
    FROM v
    WHERE identifier_mapped = 'no'
      AND sor != ''
    GROUP BY sor
    ORDER BY sor
"""

# Category D: GUID resolution rate per target concept.
# resolved = guid_in_source OR guid_fetched_by_assethub
SQL_RESOLUTION_BY_TARGET = """
    SELECT related,
           COUNT(*)                                                             AS times_referenced,
           SUM(CASE WHEN rel_guid_in_source = 'yes' THEN 1 ELSE 0 END)        AS in_source,
           SUM(CASE WHEN rel_guid_in_source != 'yes'
                     AND rel_guid_fetched   = 'yes' THEN 1 ELSE 0 END)        AS fetched,
           SUM(CASE WHEN rel_guid_in_source = 'yes'
                     OR  rel_guid_fetched   = 'yes' THEN 1 ELSE 0 END)        AS resolved,
           ROUND(
               SUM(CASE WHEN rel_guid_in_source = 'yes'
                         OR  rel_guid_fetched   = 'yes' THEN 1 ELSE 0 END)
               * 100.0 / COUNT(*), 1
           )                                                                    AS resolution_pct
    FROM v
    WHERE related != '' AND related != 'nan'
    GROUP BY related
    ORDER BY times_referenced DESC
    LIMIT 12
"""

# Overall relationship GUID state (single summary row).
SQL_OVERALL = """
    WITH rel AS (
        SELECT * FROM v
        WHERE related != '' AND related != 'nan'
    )
    SELECT
        COUNT(*)                                                                AS total,
        SUM(CASE WHEN rel_guid_in_source = 'yes' THEN 1 ELSE 0 END)           AS in_source,
        SUM(CASE WHEN rel_guid_in_source != 'yes'
                  AND rel_guid_fetched   = 'yes' THEN 1 ELSE 0 END)           AS fetched,
        COUNT(*) - SUM(CASE WHEN rel_guid_in_source = 'yes'
                             OR  rel_guid_fetched   = 'yes' THEN 1 ELSE 0 END) AS unresolved,
        ROUND(
            (COUNT(*) - SUM(CASE WHEN rel_guid_in_source = 'yes'
                                  OR  rel_guid_fetched   = 'yes'
                                  THEN 1 ELSE 0 END))
            * 100.0 / COUNT(*), 1
        )                                                                       AS unresolved_pct
    FROM rel
"""

# Relationship type breakdown (To-One vs To-Many).
SQL_BY_REL_TYPE = """
    WITH rel AS (
        SELECT * FROM v
        WHERE related != '' AND related != 'nan'
    )
    SELECT rel_type,
           COUNT(*)                                                             AS total,
           SUM(CASE WHEN rel_guid_in_source = 'yes' THEN 1 ELSE 0 END)        AS in_source,
           SUM(CASE WHEN rel_guid_in_source != 'yes'
                     AND rel_guid_fetched   = 'yes' THEN 1 ELSE 0 END)        AS fetched,
           SUM(CASE WHEN rel_guid_in_source = 'yes'
                     OR  rel_guid_fetched   = 'yes' THEN 1 ELSE 0 END)        AS resolved,
           ROUND(
               SUM(CASE WHEN rel_guid_in_source = 'yes'
                         OR  rel_guid_fetched   = 'yes' THEN 1 ELSE 0 END)
               * 100.0 / COUNT(*), 1
           )                                                                    AS resolution_pct
    FROM rel
    GROUP BY rel_type
    ORDER BY rel_type
"""

# Finding 5: IncidentNumber used informally as shadow key (44 occurrences).
# Cross-join with keyword list — standard DuckDB VALUES syntax.
SQL_KEYWORDS = """
    SELECT keyword,
           SUM(CASE WHEN comment ILIKE '%' || keyword || '%' THEN 1 ELSE 0 END) AS mentions
    FROM v,
         (VALUES ('IncidentNumber'), ('InfraRef'), ('GUID'), ('ANCHORKEY'),
                 ('legacy'), ('Trangis'), ('master')) AS kw(keyword)
    GROUP BY keyword
    HAVING mentions > 0
    ORDER BY mentions DESC
"""

# Connectivity: out-degree and in-degree per concept.
SQL_OUT_DEGREE = """
    SELECT concept, COUNT(*) AS out_degree
    FROM v
    WHERE related != '' AND related != 'nan'
    GROUP BY concept
    ORDER BY out_degree DESC
"""

SQL_IN_DEGREE = """
    SELECT related AS concept, COUNT(*) AS in_degree
    FROM v
    WHERE related != '' AND related != 'nan'
    GROUP BY related
    ORDER BY in_degree DESC
"""

# Full concept catalog: one row per concept with SoR, table, GUID, uniqueness.
SQL_CONCEPT_CATALOG = """
    SELECT DISTINCT
        concept,
        sor,
        sor_table,
        identifier_mapped   AS has_guid,
        id_unique
    FROM v
    WHERE sor != ''
    ORDER BY sor, concept
"""

# All relationships with their resolution status.
SQL_RELATIONSHIPS = """
    SELECT
        concept             AS source,
        sor                 AS source_sor,
        related             AS target,
        rel_type,
        rel_guid_in_source,
        rel_guid_fetched
    FROM v
    WHERE related != '' AND related != 'nan'
    ORDER BY sor, concept, related
"""


# ── Public API ────────────────────────────────────────────────────────────────

def run_analysis(con: duckdb.DuckDBPyConnection) -> dict:
    """
    Run all analysis queries and return a results dict consumed by the
    charting modules and write_summary().

    Parameters
    ----------
    con : open DuckDB connection from ah_loader.get_connection()

    Returns
    -------
    dict — all scalar values and DataFrames needed downstream
    """
    r = {}

    # ── Finding 1 ─────────────────────────────────────────────────────────────
    sor_df = con.execute(SQL_GUID_BY_SOR).df()
    ir = sor_df[sor_df['sor'] == 'infraref'].iloc[0]
    tr = sor_df[sor_df['sor'] == 'trangis'].iloc[0]

    r['infraref_total']    = int(ir['total'])
    r['infraref_guid_yes'] = int(ir['guid_yes'])
    r['infraref_guid_no']  = int(ir['guid_no'])
    r['infraref_guid_pct'] = float(ir['guid_pct'])
    r['trangis_total']     = int(tr['total'])
    r['trangis_guid_yes']  = 0   # always 0 — Oracle views have no GUID column
    r['trangis_guid_no']   = int(tr['guid_no'])

    # ── Category A ────────────────────────────────────────────────────────────
    non_unique_df          = con.execute(SQL_NON_UNIQUE).df()
    r['non_unique_count']  = len(non_unique_df)
    r['non_unique_concepts'] = non_unique_df.to_dict('records')

    # ── Category B ────────────────────────────────────────────────────────────
    r['dual_source_concepts'] = list(
        con.execute(SQL_DUAL_SOURCE).df()['concept']
    )

    # ── Category C ────────────────────────────────────────────────────────────
    no_guid_df             = con.execute(SQL_NO_GUID).df()
    r['no_guid_total']     = int(no_guid_df['count'].sum())
    ir_row = no_guid_df[no_guid_df['sor'] == 'infraref']
    tr_row = no_guid_df[no_guid_df['sor'] == 'trangis']
    r['no_guid_infraref']       = int(ir_row['count'].iloc[0]) if len(ir_row) else 0
    r['no_guid_trangis']        = int(tr_row['count'].iloc[0]) if len(tr_row) else 0
    r['no_guid_infraref_names'] = (
        ir_row['concepts'].iloc[0].split(', ') if len(ir_row) else []
    )

    # ── Category D ────────────────────────────────────────────────────────────
    overall                 = con.execute(SQL_OVERALL).df().iloc[0]
    r['rel_total']          = int(overall['total'])
    r['rel_avail']          = int(overall['in_source'])
    r['rel_fetched']        = int(overall['fetched'])
    r['rel_unresolved']     = int(overall['unresolved'])
    r['rel_unresolved_pct'] = float(overall['unresolved_pct'])

    r['target_stats']       = con.execute(SQL_RESOLUTION_BY_TARGET).df()
    r['rel_type_stats']     = con.execute(SQL_BY_REL_TYPE).df()

    # ── Graph connectivity ────────────────────────────────────────────────────
    r['out_degree']         = con.execute(SQL_OUT_DEGREE).df()
    r['in_degree']          = con.execute(SQL_IN_DEGREE).df()

    # ── Comment keywords ──────────────────────────────────────────────────────
    kw_df                   = con.execute(SQL_KEYWORDS).df()
    r['keyword_counts']     = dict(zip(kw_df['keyword'], kw_df['mentions'].astype(int)))

    # ── Full catalog + relationships (for markdown graph) ────────────────
    r['concept_catalog']    = con.execute(SQL_CONCEPT_CATALOG).df()
    r['relationships']      = con.execute(SQL_RELATIONSHIPS).df()

    return r


def write_summary(results: dict, out_path: str, previous: dict | None = None):
    """
    Generate a narrative report via the Claude API (with run history for
    delta comparison) and write it to a plain-text file.

    Falls back to a structured report if ANTHROPIC_API_KEY is not set.
    """
    from ah_narrative import generate_narrative

    text = generate_narrative(results, INPUT_FILE, previous=previous)

    with open(out_path, 'w') as f:
        f.write(text)
    print(f"  ✓  {out_path}")