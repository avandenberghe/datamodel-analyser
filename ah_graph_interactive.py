"""
ah_graph_interactive.py — Interactive Asset Hub Graph
=====================================================
Generates a standalone HTML file with a zoomable, pannable, draggable
graph using pyvis (vis.js under the hood).

Usage:
    python ah_graph_interactive.py                  # all systems, first run
    python ah_graph_interactive.py --sor infraref   # single system
    python ah_graph_interactive.py --run-id 1       # specific run
"""

import argparse
import duckdb
from pyvis.network import Network

from ah_loader import DB_FILE

# ── Palette ──────────────────────────────────────────────────────────────────
C_IR      = '#1A7A5E'
C_TR      = '#B03A2E'
C_DUAL    = '#17A2B8'
C_WARN    = '#F1C40F'
C_IR_EDGE = '#2EAD82'
C_TR_EDGE = '#E74C3C'
C_DUAL_EDGE = '#17A2B8'


def build_interactive_graph(out_path: str = 'outputs/graph.html',
                            run_id: int | None = None,
                            sor_filter: str | None = None):
    """Build an interactive HTML graph."""
    con = duckdb.connect(DB_FILE, read_only=True)

    if run_id is None:
        run_id = con.execute("SELECT MIN(run_id) FROM runs").fetchone()[0]

    run_ts = str(con.execute(
        "SELECT timestamp FROM runs WHERE run_id = ?", [run_id]
    ).fetchone()[0])[:19]

    # ── Load concepts ────────────────────────────────────────────────────────
    concepts = con.execute("""
        SELECT concept, sor, identifier_mapped, id_unique
        FROM concepts WHERE run_id = ?
    """, [run_id]).fetchdf()

    sor_map = {}
    guid_map = {}
    unique_map = {}
    sor_table_map = {}

    for _, row in concepts.iterrows():
        c, s = row['concept'], row['sor']
        if c in sor_map and sor_map[c] != s:
            sor_map[c] = 'dual'
        else:
            sor_map[c] = s
        has_guid = str(row['identifier_mapped']).lower() == 'yes'
        is_unique = str(row['id_unique']).lower() == 'yes'
        if c in guid_map:
            guid_map[c] = guid_map[c] and has_guid
            unique_map[c] = unique_map[c] and is_unique
        else:
            guid_map[c] = has_guid
            unique_map[c] = is_unique

    # ── Load relationships ───────────────────────────────────────────────────
    rels = con.execute("""
        SELECT concept, sor, related, rel_type
        FROM relationships WHERE run_id = ?
    """, [run_id]).fetchdf()

    con.close()

    # ── Build edge list (deduplicated) ───────────────────────────────────────
    seen = set()
    edges = []
    for _, row in rels.iterrows():
        src, tgt = row['concept'], row['related']
        rel = str(row['rel_type']).lower().strip()
        key = (src, tgt)
        if key not in seen:
            seen.add(key)
            edges.append((src, tgt, rel, row['sor']))

    # Fill in unknowns for relationship targets not in concepts table
    for _, tgt, _, _ in edges:
        if tgt not in sor_map:
            sor_map[tgt] = 'unknown'
            guid_map[tgt] = False
            unique_map[tgt] = True

    # ── SoR filter ───────────────────────────────────────────────────────────
    if sor_filter:
        keep = {c for c in sor_map if sor_map[c] in (sor_filter, 'dual')}
        for src, tgt, _, _ in edges:
            if src in keep:
                keep.add(tgt)
        sor_map = {c: s for c, s in sor_map.items() if c in keep}
        edges = [(s, t, r, sr) for s, t, r, sr in edges
                 if s in keep and t in keep]

    # ── Compute in-degree ────────────────────────────────────────────────────
    in_deg = {}
    for _, tgt, _, _ in edges:
        in_deg[tgt] = in_deg.get(tgt, 0) + 1
    max_deg = max(in_deg.values()) if in_deg else 1

    # ── Build pyvis network ──────────────────────────────────────────────────
    sor_label = {'infraref': 'InfraRef', 'trangis': 'Trangis'}.get(
        sor_filter, 'All Systems')
    title = f'Asset Hub, {sor_label}, Run #{run_id}'

    net = Network(
        height='100vh', width='100%',
        bgcolor='#FAFAFA', font_color='#1C2833',
        directed=True, notebook=False,
        heading='',
    )

    # Physics settings for a clean layout
    net.set_options('''{
        "physics": {
            "forceAtlas2Based": {
                "gravitationalConstant": -80,
                "centralGravity": 0.008,
                "springLength": 180,
                "springConstant": 0.02,
                "damping": 0.5
            },
            "solver": "forceAtlas2Based",
            "stabilization": {
                "iterations": 300
            }
        },
        "nodes": {
            "font": {
                "size": 12,
                "face": "Amazon Ember, Calibri, sans-serif",
                "strokeWidth": 3,
                "strokeColor": "#FAFAFA"
            },
            "borderWidth": 2,
            "shadow": true
        },
        "edges": {
            "smooth": {
                "type": "continuous",
                "forceDirection": "none"
            },
            "arrows": {
                "to": { "enabled": true, "scaleFactor": 0.5 }
            },
            "color": { "opacity": 0.4 },
            "width": 1
        },
        "interaction": {
            "hover": true,
            "tooltipDelay": 100,
            "navigationButtons": true,
            "keyboard": true
        }
    }''')

    # ── Add nodes ────────────────────────────────────────────────────────────
    for c in sor_map:
        s = sor_map[c]
        deg = in_deg.get(c, 0)
        has_guid = guid_map.get(c, False)
        is_unique = unique_map.get(c, True)
        has_issue = not has_guid or not is_unique

        # Colour
        if s == 'dual':
            color = C_DUAL
        elif s == 'trangis':
            color = C_TR
        elif s == 'infraref':
            color = C_IR
        else:
            color = '#888888'

        border = C_WARN if has_issue else color

        # Size: 8-50 based on in-degree
        frac = deg / max(max_deg, 1)
        size = 8 + frac * frac * 42

        # Tooltip
        issues = []
        if not has_guid:
            issues.append('No GUID')
        if not is_unique:
            issues.append('Non-unique ID')
        issue_str = ', '.join(issues) if issues else 'None'

        tooltip = (
            f"{c}\n"
            f"Source: {s}\n"
            f"In-degree: {deg}\n"
            f"GUID: {'Yes' if has_guid else 'No'}\n"
            f"Unique ID: {'Yes' if is_unique else 'No'}\n"
            f"Issues: {issue_str}"
        )

        # Label: show for hubs and flagged nodes, hide for small leaf nodes
        label = c if deg >= 3 or has_issue or s == 'dual' else ''

        net.add_node(
            c, label=label, title=tooltip, size=size,
            color={'background': color, 'border': border,
                   'highlight': {'background': color, 'border': '#FFD700'}},
            font={'size': 14 if deg >= 10 else 11},
        )

    # ── Add edges ────────────────────────────────────────────────────────────
    for src, tgt, rel, sor in edges:
        s = sor_map.get(src, 'unknown')
        if s == 'dual':
            ec = C_DUAL_EDGE
        elif s == 'trangis':
            ec = C_TR_EDGE
        else:
            ec = C_IR_EDGE

        dashes = 'many' in rel
        tooltip = f"{src} → {tgt} ({rel})"

        net.add_edge(
            src, tgt,
            color=ec, dashes=dashes,
            title=tooltip,
        )

    # ── Save ─────────────────────────────────────────────────────────────────
    net.save_graph(out_path)

    # Inject a single title into the HTML
    with open(out_path, 'r') as f:
        html = f.read()
    html = html.replace(
        '<center>\n<h1></h1>\n</center>',
        f'<center><h1 style="font-family: Amazon Ember, Calibri, sans-serif; '
        f'color: #232F3E; padding: 12px 0 0 0;">{title}</h1></center>',
        1  # replace only first occurrence
    )
    # Remove the second empty heading pyvis inserts
    html = html.replace(
        '<center>\n          <h1></h1></center>',
        ''
    )
    with open(out_path, 'w') as f:
        f.write(html)

    print(f"  ✓  {out_path}  ({len(sor_map)} nodes, {len(edges)} edges)")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Generate interactive Asset Hub graph')
    parser.add_argument('--run-id', type=int, default=None)
    parser.add_argument('--sor', choices=['infraref', 'trangis'], default=None)
    args = parser.parse_args()

    build_interactive_graph(run_id=args.run_id, sor_filter=args.sor)
    build_interactive_graph(
        out_path='outputs/graph_infraref.html',
        run_id=args.run_id, sor_filter='infraref')
    build_interactive_graph(
        out_path='outputs/graph_trangis.html',
        run_id=args.run_id, sor_filter='trangis')
