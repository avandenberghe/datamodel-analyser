"""
ah_graph.py — Asset Hub Data Graph Visualization
=================================================
Builds a directed graph from concepts (nodes) and relationships (edges)
stored in the DuckDB database for a given run, then renders it as a PNG.

Node appearance encodes:
  - colour  → source system (InfraRef / Trangis / dual-source)
  - size    → in-degree (how many concepts point to it)
  - border  → yellow ring = data quality issue (no GUID or non-unique ID)

Edge appearance encodes:
  - solid   → "to one" relationship
  - dashed  → "to many" relationship
  - colour  → follows source node colour
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx
import duckdb

from ah_loader import DB_FILE, DPI

# ── Palette ──────────────────────────────────────────────────────────────────
C_IR       = '#1A7A5E'   # InfraRef green
C_IR_EDGE  = '#2EAD82'
C_TR       = '#B03A2E'   # Trangis red
C_TR_EDGE  = '#E74C3C'
C_DUAL     = '#17A2B8'   # Dual-source turquoise
C_WARN     = '#F1C40F'   # Yellow ring for issues
C_BG       = '#FAFAFA'
C_TITLE    = '#1C2833'
C_SUBTITLE = '#566573'


def plot_graph(out_path: str, run_id: int | None = None,
               sor_filter: str | None = None):
    """
    Build a directed graph from the database and render it to out_path.
    If run_id is None, uses the first run.
    If sor_filter is set ('infraref' or 'trangis'), only include concepts
    and relationships from that source system (plus dual-source nodes).
    """
    con = duckdb.connect(DB_FILE, read_only=True)

    # Resolve run_id
    if run_id is None:
        run_id = con.execute(
            "SELECT MIN(run_id) FROM runs"
        ).fetchone()[0]

    run_ts = con.execute(
        "SELECT timestamp FROM runs WHERE run_id = ?", [run_id]
    ).fetchone()[0]

    # ── Load concepts ────────────────────────────────────────────────────────
    concepts = con.execute("""
        SELECT concept, sor, identifier_mapped, id_unique
        FROM concepts
        WHERE run_id = ?
    """, [run_id]).fetchdf()

    # Build SoR lookup — a concept appearing in both systems is dual-source
    sor_map = {}        # concept → 'infraref' | 'trangis' | 'dual'
    guid_map = {}       # concept → bool (has GUID)
    unique_map = {}     # concept → bool (ID is unique)
    for _, row in concepts.iterrows():
        c = row['concept']
        s = row['sor']
        if c in sor_map and sor_map[c] != s:
            sor_map[c] = 'dual'
        else:
            sor_map[c] = s
        # Keep the "worst" value if dual-source
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
        FROM relationships
        WHERE run_id = ?
    """, [run_id]).fetchdf()

    con.close()

    # ── Build NetworkX graph ─────────────────────────────────────────────────
    G = nx.DiGraph()

    # Add all concept nodes
    for c in sor_map:
        G.add_node(c)

    # Add edges (deduplicate since some appear twice)
    seen_edges = set()
    edge_styles = {}
    for _, row in rels.iterrows():
        src, tgt = row['concept'], row['related']
        rel = str(row['rel_type']).lower().strip()
        key = (src, tgt)
        if key not in seen_edges:
            seen_edges.add(key)
            G.add_edge(src, tgt)
            edge_styles[key] = 'to many' if 'many' in rel else 'to one'

    # Some relationship targets may not be in the concepts table
    # (typos or cross-system references) — add them as unknowns
    for n in G.nodes():
        if n not in sor_map:
            sor_map[n] = 'unknown'
            guid_map[n] = False
            unique_map[n] = True

    # ── SoR filter ──────────────────────────────────────────────────────────
    if sor_filter:
        keep = {n for n in G.nodes()
                if sor_map.get(n) in (sor_filter, 'dual')}
        # Also keep relationship targets referenced by kept nodes
        for u, v in list(G.edges()):
            if u in keep:
                keep.add(v)
        remove = set(G.nodes()) - keep
        G.remove_nodes_from(remove)

    # ── Layout ───────────────────────────────────────────────────────────────
    # Spring layout with SoR-based seeding for clustering
    import random
    random.seed(42)

    init_pos = {}
    for n in G.nodes():
        s = sor_map.get(n, 'unknown')
        deg = G.in_degree(n)
        if s == 'infraref':
            x, y = random.gauss(-3, 1.2), random.gauss(0, 2)
        elif s == 'trangis':
            x, y = random.gauss(3, 1.2), random.gauss(0, 2)
        elif s == 'dual':
            x, y = random.gauss(0, 0.3), random.gauss(3, 0.3)
        else:
            x, y = random.gauss(0, 1), random.gauss(-3, 1)
        # Pull high-degree nodes toward center
        if deg > 15:
            x *= 0.3
            y += 1.0
        init_pos[n] = (x, y)

    pos = nx.spring_layout(
        G, pos=init_pos, k=2.8, iterations=300, seed=42
    )

    # Compress outliers toward the main cluster (soft clamp)
    import numpy as np
    xs = np.array([pos[n][0] for n in pos])
    ys = np.array([pos[n][1] for n in pos])
    cx, cy = np.median(xs), np.median(ys)
    for n in pos:
        dx, dy = pos[n][0] - cx, pos[n][1] - cy
        dist = (dx**2 + dy**2) ** 0.5
        if dist > 3.0:
            scale = 3.0 / dist * 0.7 + 0.3
            pos[n] = (cx + dx * scale, cy + dy * scale)

    # ── Compute visual properties ────────────────────────────────────────────
    in_degrees = dict(G.in_degree())
    max_deg = max(in_degrees.values()) if in_degrees else 1

    node_colors = []
    node_edge_colors = []
    node_sizes = []
    for n in G.nodes():
        s = sor_map.get(n, 'unknown')
        has_issue = not guid_map.get(n, False) or not unique_map.get(n, True)

        if s == 'dual':
            node_colors.append(C_DUAL)
        elif s == 'trangis':
            node_colors.append(C_TR)
        else:
            node_colors.append(C_IR)

        node_edge_colors.append(C_WARN if has_issue else '#FFFFFF88')

        # Size: 60–900 based on in-degree (quadratic scaling for contrast)
        deg = in_degrees.get(n, 0)
        frac = deg / max(max_deg, 1)
        size = 60 + frac * frac * 840
        node_sizes.append(size)

    edge_colors = []
    edge_styles_list = []
    for u, v in G.edges():
        s = sor_map.get(u, 'unknown')
        if s == 'dual':
            edge_colors.append(C_DUAL)
        elif s == 'trangis':
            edge_colors.append(C_TR_EDGE)
        else:
            edge_colors.append(C_IR_EDGE)

        style = edge_styles.get((u, v), 'to one')
        edge_styles_list.append('dashed' if 'many' in style else 'solid')

    # ── Render ───────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(22, 16))
    fig.patch.set_facecolor(C_BG)
    ax.set_facecolor(C_BG)

    # Draw edges grouped by style (networkx doesn't support per-edge style
    # in a single draw call)
    solid_edges = [(u, v) for (u, v), s in zip(G.edges(), edge_styles_list)
                   if s == 'solid']
    dashed_edges = [(u, v) for (u, v), s in zip(G.edges(), edge_styles_list)
                    if s == 'dashed']
    solid_colors = [c for c, s in zip(edge_colors, edge_styles_list)
                    if s == 'solid']
    dashed_colors = [c for c, s in zip(edge_colors, edge_styles_list)
                     if s == 'dashed']

    nx.draw_networkx_edges(
        G, pos, edgelist=solid_edges, edge_color=solid_colors,
        alpha=0.35, width=0.7, arrows=True, arrowsize=8,
        connectionstyle='arc3,rad=0.05', ax=ax
    )
    nx.draw_networkx_edges(
        G, pos, edgelist=dashed_edges, edge_color=dashed_colors,
        alpha=0.35, width=0.7, arrows=True, arrowsize=8,
        style='dashed', connectionstyle='arc3,rad=0.05', ax=ax
    )

    # Draw nodes
    nx.draw_networkx_nodes(
        G, pos, node_color=node_colors, node_size=node_sizes,
        edgecolors=node_edge_colors, linewidths=1.5, alpha=0.9, ax=ax
    )

    # Labels — offset above node, scaled to layout
    y_range = max(p[1] for p in pos.values()) - min(p[1] for p in pos.values())
    label_offset = y_range * 0.02
    label_pos = {n: (x, y + label_offset) for n, (x, y) in pos.items()}

    # Tier 1: high in-degree hubs — always labelled, larger font
    hub_thresh = 4 if sor_filter else 10
    hub_labels = {n: n for n in G.nodes() if in_degrees.get(n, 0) >= hub_thresh}
    # Tier 2: medium in-degree or special status
    mid_thresh = 1 if sor_filter else 3
    mid_labels = {n: n for n in G.nodes()
                  if n not in hub_labels and (
                      in_degrees.get(n, 0) >= mid_thresh
                      or sor_map.get(n) == 'dual'
                      or not unique_map.get(n, True)
                  )}

    nx.draw_networkx_labels(
        G, label_pos, labels=hub_labels, font_size=7.5, font_weight='bold',
        font_color=C_TITLE, ax=ax
    )
    nx.draw_networkx_labels(
        G, label_pos, labels=mid_labels, font_size=5.5, font_weight='bold',
        font_color=C_SUBTITLE, ax=ax
    )

    # ── Title & subtitle ─────────────────────────────────────────────────────
    sor_label = {'infraref': 'InfraRef', 'trangis': 'Trangis'}.get(sor_filter, '')
    title_text = f'Asset Hub — {sor_label} Concept Graph' if sor_label else \
                 'Asset Hub — Concept Relationship Graph'
    ax.set_title(
        title_text,
        fontsize=16, fontweight='bold', color=C_TITLE, pad=20
    )
    ax.text(
        0.5, 1.01,
        f'Run #{run_id}  ·  {len(G.nodes())} concepts  ·  '
        f'{len(G.edges())} relationships  ·  {str(run_ts)[:19]}',
        transform=ax.transAxes, ha='center', va='bottom',
        fontsize=9, color=C_SUBTITLE, style='italic'
    )

    # ── Legend ────────────────────────────────────────────────────────────────
    legend_handles = [
        mpatches.Patch(facecolor=C_IR, edgecolor='white', label='InfraRef'),
        mpatches.Patch(facecolor=C_TR, edgecolor='white', label='Trangis'),
        mpatches.Patch(facecolor=C_DUAL, edgecolor='white', label='Dual-source'),
        mpatches.Patch(facecolor='#DDDDDD', edgecolor=C_WARN, linewidth=2,
                       label='Data quality issue (no GUID / non-unique)'),
        plt.Line2D([0], [0], color=C_IR_EDGE, linewidth=1.2,
                   label='To-one relationship'),
        plt.Line2D([0], [0], color=C_IR_EDGE, linewidth=1.2, linestyle='dashed',
                   label='To-many relationship'),
    ]
    ax.legend(
        handles=legend_handles, loc='lower left', fontsize=8,
        framealpha=0.9, edgecolor=C_SUBTITLE
    )

    ax.axis('off')
    plt.tight_layout(pad=1.0)
    plt.savefig(out_path, dpi=DPI, bbox_inches='tight', facecolor=C_BG)
    plt.close()
    print(f"  ✓  {out_path}")


if __name__ == '__main__':
    plot_graph('outputs/graph.png')
    plot_graph('outputs/graph_infraref.png', sor_filter='infraref')
    plot_graph('outputs/graph_trangis.png', sor_filter='trangis')
