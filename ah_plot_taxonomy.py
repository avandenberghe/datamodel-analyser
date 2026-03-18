"""
ah_plot_taxonomy.py — Asset Hub ID Analysis
=============================================
Graphic 1: Five-bucket severity taxonomy.
Intended for mail 1 (briefing to architecture colleagues).
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from ah_loader import DPI

# Palette
C_WHITE = '#FFFFFF'
C_DARK  = '#1C2833'
C_GRAY  = '#566573'
C_BORD  = '#BDC3C7'


def plot_taxonomy(results: dict, out_path: str):
    """
    Horizontal bucket diagram — one row per category A–E.

    Left column: letter badge + severity label + title + body text.
    Right column: concise detail / examples (italic).
    Count displayed right-aligned in each row.
    """
    buckets = [
        {
            'label': 'A', 'severity': 'CONTRACT VIOLATION',
            'title': 'Non-unique keys',
            'count': f"{results['non_unique_count']} concepts",
            'body': (
                "The exposed 'id' field is not unique.\n"
                "Any consumer using it as a lookup key\n"
                "may silently operate on the wrong asset."
            ),
            'detail': (
                "GeographicalBay · PowerTransformerPlace (InfraRef — fixable)\n"
                "Line · GuardCircuit (Trangis — unresolvable in v1)"
            ),
            'color': '#C0392B',
        },
        {
            'label': 'B', 'severity': 'INTEGRITY FAILURE',
            'title': 'Inconsistent key space',
            'count': '1 concept',
            'body': (
                "GeographicalSite is sourced from both\n"
                "Trangis and InfraRef simultaneously.\n"
                "No data master defined."
            ),
            'detail': (
                "Same real-world site can appear under different\n"
                "keys depending on source of record — consumers\n"
                "cannot reliably identify the same physical object."
            ),
            'color': '#D35400',
        },
        {
            'label': 'C', 'severity': 'COMPLETENESS FAILURE',
            'title': 'No stable cross-system identifier',
            'count': f"{results['no_guid_total']} concepts",
            'body': (
                f"{results['no_guid_trangis']} Trangis concepts "
                "(Oracle VIEW_* — non-alterable,\n"
                f"Trangis in decom) + {results['no_guid_infraref']} InfraRef exceptions.\n"
                "No GUID exists in the source at all."
            ),
            'detail': (
                "Not fixable in v1. Resolves only via migration\n"
                "to replacement SoR: LAS / SUB / SECSYS / TnB.\n"
                "Trangis views cannot be altered."
            ),
            'color': '#E67E22',
        },
        {
            'label': 'D', 'severity': 'CASCADING EFFECT',
            'title': 'Relationship-level GUID unavailability',
            'count': (
                f"{results['rel_unresolved']} / {results['rel_total']} links "
                f"({results['rel_unresolved_pct']}%)"
            ),
            'body': (
                "When Asset Hub links concepts, the related\n"
                "concept's GUID is unavailable at link time\n"
                f"in {results['rel_unresolved_pct']}% of cases."
            ),
            'detail': (
                "Asset graph navigable only via WorkCenter (100%).\n"
                "All topological hubs resolve at <5%.\n"
                "Direct consequence of categories B and C."
            ),
            'color': '#2471A3',
        },
        {
            'label': 'E', 'severity': 'BOUNDARY GAP',
            'title': "Outside Asset Hub's control",
            'count': '5 message types',
            'body': (
                "APMO-originated messages carry only 'id'.\n"
                "Asset Hub cannot enrich what it does\n"
                "not publish."
            ),
            'detail': (
                "CreateWork · AssetHealthIndexPublished\n"
                "InfrastructureNeedCreated/Updated\n"
                "Checklist flows (no Asset Hub integration)"
            ),
            'color': '#566573',
        },
    ]

    fig, ax = plt.subplots(figsize=(11, 7.5))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 7.5)
    ax.axis('off')
    fig.patch.set_facecolor(C_WHITE)

    ax.text(5.5, 7.15, 'Asset Hub — ID Issue Taxonomy',
            ha='center', va='center', fontsize=15,
            fontweight='bold', color=C_DARK)
    ax.text(5.5, 6.78, 'Five categories of identifier failure, ordered by severity',
            ha='center', va='center', fontsize=9, color=C_GRAY)

    BOX_H       = 1.05
    BOX_W       = 10.0
    X0          = 0.5
    y_positions = [5.6, 4.35, 3.1, 1.85, 0.6]

    for b, y in zip(buckets, y_positions):
        col = b['color']

        # Main box
        ax.add_patch(FancyBboxPatch(
            (X0, y), BOX_W, BOX_H,
            boxstyle='round,pad=0.04',
            facecolor='#FDFEFE', edgecolor=col,
            linewidth=1.4, zorder=2
        ))
        # Coloured left bar
        ax.add_patch(FancyBboxPatch(
            (X0, y), 0.38, BOX_H,
            boxstyle='round,pad=0.0',
            facecolor=col, edgecolor='none', zorder=3
        ))
        # Letter
        ax.text(X0 + 0.19, y + BOX_H / 2, b['label'],
                ha='center', va='center', fontsize=16,
                fontweight='bold', color=C_WHITE, zorder=4)
        # Severity label
        ax.text(X0 + 0.55, y + BOX_H - 0.18, b['severity'],
                ha='left', va='center', fontsize=6.5,
                fontweight='bold', color=col, style='italic', zorder=4)
        # Title
        ax.text(X0 + 0.55, y + BOX_H / 2 + 0.05, b['title'],
                ha='left', va='center', fontsize=10,
                fontweight='bold', color=C_DARK, zorder=4)
        # Count (right-aligned)
        ax.text(X0 + BOX_W - 0.12, y + BOX_H / 2 + 0.05, b['count'],
                ha='right', va='center', fontsize=8.5,
                fontweight='bold', color=col, zorder=4)
        # Body text (left column)
        ax.text(X0 + 0.55, y + 0.17, b['body'],
                ha='left', va='center', fontsize=7.2,
                color='#444', zorder=4, linespacing=1.4)
        # Detail text (right column)
        ax.text(X0 + 5.8, y + BOX_H / 2, b['detail'],
                ha='left', va='center', fontsize=7.0,
                color=C_GRAY, style='italic', zorder=4, linespacing=1.45)
        # Divider
        ax.plot(
            [X0 + 5.7, X0 + 5.7], [y + 0.12, y + BOX_H - 0.12],
            color=C_BORD, lw=0.7, zorder=3
        )

    ax.text(
        5.5, 0.22,
        'Categories B–E remain open regardless of the proposed v1 interim fix  ·  '
        'Asset Hub ID Analysis, 17 March 2026',
        ha='center', va='center', fontsize=7, color=C_GRAY, style='italic'
    )

    plt.tight_layout(pad=0.3)
    plt.savefig(out_path, dpi=DPI, bbox_inches='tight', facecolor=C_WHITE)
    plt.close()
    print(f"  ✓  {out_path}")