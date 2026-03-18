"""
ah_graph_md.py — Asset Hub Property Graph as Markdown
=====================================================
Replaces the matplotlib PNG property graph with a structured markdown
document. Every concept and relationship is listed with its source,
GUID status, uniqueness, and connectivity — no visual interpretation
required.
"""

import pandas as pd


def write_property_graph_md(results: dict, out_path: str):
    """
    Generate a markdown property graph from the analysis results.
    Groups concepts by source system, shows GUID/uniqueness status,
    then lists all relationships with resolution state.
    """
    catalog = results['concept_catalog']
    rels    = results['relationships']
    in_deg  = results['in_degree']
    out_deg = results['out_degree']
    dual    = set(results['dual_source_concepts'])
    non_uniq = {c['concept'] for c in results['non_unique_concepts']}

    # build degree lookup dicts
    in_map  = dict(zip(in_deg['concept'], in_deg['in_degree'].astype(int))) \
        if len(in_deg) else {}
    out_map = dict(zip(out_deg['concept'], out_deg['out_degree'].astype(int))) \
        if len(out_deg) else {}

    lines = [
        '# Asset Hub — Property Graph',
        '',
        'Structured view of all concepts and relationships by source system.',
        'Every entry is derived from the source data — nothing is inferred.',
        '',
    ]

    # ── Concept catalog by SoR ───────────────────────────────────────────
    sor_groups = [
        ('infraref', 'InfraRef (MSSQL)'),
        ('trangis',  'Trangis (Oracle views — read-only, in decommissioning)'),
    ]

    for sor_key, sor_label in sor_groups:
        group = catalog[catalog['sor'] == sor_key].copy()
        if group.empty:
            continue

        lines += [
            f'## {sor_label}',
            '',
            f'{len(group)} concepts',
            '',
            '| Concept | Source Table | GUID | Unique ID | In-degree | Out-degree | Flags |',
            '|---------|-------------|------|-----------|-----------|------------|-------|',
        ]

        for _, row in group.iterrows():
            concept = row['concept']
            table   = row['sor_table']
            guid    = 'yes' if row['has_guid'] == 'yes' else 'NO'
            unique  = 'yes' if row['id_unique'] == 'yes' else 'NO'
            ind     = in_map.get(concept, 0)
            outd    = out_map.get(concept, 0)

            flags = []
            if concept in non_uniq:
                flags.append('NON-UNIQUE ID')
            if concept in dual:
                flags.append('DUAL-SOURCE')
            if guid == 'NO':
                flags.append('NO GUID')
            flag_str = ', '.join(flags) if flags else ''

            lines.append(
                f'| {concept} | {table} | {guid} | {unique} '
                f'| {ind} | {outd} | {flag_str} |'
            )

        lines.append('')

    # ── Dual-source concepts ─────────────────────────────────────────────
    if dual:
        lines += [
            '## Dual-Source Concepts',
            '',
            'These concepts appear in both InfraRef and Trangis, creating '
            'mastery ambiguity:',
            '',
        ]
        for c in sorted(dual):
            lines.append(f'- **{c}**')
        lines.append('')

    # ── Relationships ────────────────────────────────────────────────────
    lines += [
        '## Relationships',
        '',
        f'{len(rels)} relationships total.',
        '',
        '| Source | Source SoR | Target | Type | GUID in Source | Fetched by AH | Resolved |',
        '|--------|-----------|--------|------|---------------|---------------|----------|',
    ]

    for _, row in rels.iterrows():
        src     = row['source']
        src_sor = row['source_sor']
        tgt     = row['target']
        rtype   = row['rel_type']
        in_src  = row['rel_guid_in_source']
        fetched = row['rel_guid_fetched']
        resolved = 'yes' if in_src == 'yes' or fetched == 'yes' else 'NO'

        lines.append(
            f'| {src} | {src_sor} | {tgt} | {rtype} '
            f'| {in_src} | {fetched} | {resolved} |'
        )

    lines.append('')

    # ── Summary stats ────────────────────────────────────────────────────
    total_rels   = len(rels)
    resolved_ct  = len(rels[
        (rels['rel_guid_in_source'] == 'yes') |
        (rels['rel_guid_fetched'] == 'yes')
    ])
    unresolved   = total_rels - resolved_ct
    unres_pct    = round(unresolved * 100.0 / total_rels, 1) if total_rels else 0

    lines += [
        '## Relationship Resolution Summary',
        '',
        f'| Metric | Count | % |',
        f'|--------|------:|--:|',
        f'| Total relationships | {total_rels} | |',
        f'| Resolved | {resolved_ct} | {100.0 - unres_pct}% |',
        f'| Unresolved | {unresolved} | {unres_pct}% |',
        '',
    ]

    with open(out_path, 'w') as f:
        f.write('\n'.join(lines))
    print(f"  ✓  {out_path}")
