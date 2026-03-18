"""
ah_plot_resolution.py — Asset Hub ID Analysis
===============================================
Graphic 3: GUID resolution rate per target concept (bar chart)
           + overall GUID state across all relationships (donut).
Intended for mail 2 (strategic concerns).

Key finding surfaced by this chart:
  WorkCenter is the only reliably resolvable target at 100%.
  Every other high-frequency target resolves below 5%.
  84% of all relationship links carry no resolvable GUID.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from ah_loader import DPI

# Palette
C_WHITE = '#FFFFFF'
C_DARK  = '#1C2833'
C_GRAY  = '#566573'
C_GREEN = '#1A7A5E'
C_RED   = '#C0392B'
C_AMBER = '#D35400'


def plot_resolution(results: dict, out_path: str):
    """
    Two-panel figure:
      Left  — horizontal bar chart: bar length = times referenced,
               green/amber/red fill = resolved portion.
      Right — donut: unresolved / in-source / fetched breakdown.
    """
    fig, axes = plt.subplots(
        1, 2, figsize=(13, 6.5),
        gridspec_kw={'width_ratios': [1.6, 1]}
    )
    fig.patch.set_facecolor(C_WHITE)

    _draw_bar_chart(axes[0], results)
    _draw_donut(axes[1], results)

    fig.suptitle(
        'Asset Hub — Relationship-Level GUID Resolution Analysis',
        fontsize=12, fontweight='bold', color=C_DARK, y=1.01
    )
    fig.text(
        0.5, -0.02,
        f"{results['rel_unresolved_pct']}% of all relationship links cannot "
        'carry a resolvable identifier across system boundaries  ·  '
        'Asset Hub ID Analysis, 17 March 2026',
        ha='center', fontsize=7.5, color=C_GRAY, style='italic'
    )

    plt.tight_layout(pad=1.5)
    plt.savefig(out_path, dpi=DPI, bbox_inches='tight', facecolor=C_WHITE)
    plt.close()
    print(f"  ✓  {out_path}")


def _draw_bar_chart(ax, results: dict):
    """Horizontal bar chart — resolution rate per target concept."""
    ax.set_facecolor(C_WHITE)

    ts       = results['target_stats']
    concepts = list(ts['related'])[::-1]
    totals   = list(ts['times_referenced'])[::-1]
    resolved = list(ts['resolved'])[::-1]
    rates    = [r / t * 100 for r, t in zip(resolved, totals)]
    y_pos    = np.arange(len(concepts))

    for i, (t, r, rate) in enumerate(zip(totals, resolved, rates)):
        # Unresolved background bar
        ax.barh(i, t, 0.55, color='#EAECEE', edgecolor='#BDC3C7', linewidth=0.5)
        # Resolved foreground bar
        col = C_GREEN if rate > 50 else (C_AMBER if rate > 10 else C_RED)
        ax.barh(i, r, 0.55, color=col, edgecolor='none')
        # Rate label
        ax.text(t + 0.8, i, f'{rate:.0f}%',
                va='center', ha='left', fontsize=8,
                fontweight='bold', color=col)
        # Reference count
        ax.text(-0.8, i, f'[{t}×]',
                va='center', ha='right', fontsize=7, color=C_GRAY)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(concepts, fontsize=9)
    ax.set_xlabel('Times referenced as relationship target',
                  fontsize=8.5, color=C_GRAY)
    ax.set_xlim(-5, 60)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.tick_params(left=False, colors=C_DARK)
    ax.tick_params(axis='x', colors=C_GRAY, labelsize=8)
    ax.set_title(
        'GUID resolution rate per target concept\n'
        'Bar length = times referenced  ·  colour fill = resolved',
        fontsize=10, fontweight='bold', color=C_DARK, pad=10
    )
    ax.legend(
        handles=[
            mpatches.Patch(color=C_GREEN, label='100% resolved'),
            mpatches.Patch(color=C_AMBER, label='50% resolved'),
            mpatches.Patch(color=C_RED,   label='<5% resolved'),
            mpatches.Patch(color='#EAECEE', label='Unresolved portion'),
        ],
        fontsize=7.5, loc='lower right', framealpha=0.9, edgecolor=C_GRAY
    )


def _draw_donut(ax, results: dict):
    """Donut chart — overall GUID state across all relationships."""
    ax.set_facecolor(C_WHITE)
    ax.set_aspect('equal')

    sizes  = [results['rel_unresolved'], results['rel_avail'], results['rel_fetched']]
    colors = [C_RED, C_GREEN, C_AMBER]
    labels = [
        f"Unresolved\n{results['rel_unresolved']}  ({results['rel_unresolved_pct']}%)",
        f"GUID in source\n{results['rel_avail']}  "
        f"({results['rel_avail'] / results['rel_total'] * 100:.0f}%)",
        f"Fetched by\nAsset Hub\n{results['rel_fetched']}  "
        f"({results['rel_fetched'] / results['rel_total'] * 100:.0f}%)",
    ]

    ax.pie(
        sizes, colors=colors, explode=(0.03, 0.03, 0.03),
        startangle=90, counterclock=False,
        wedgeprops=dict(width=0.52, edgecolor=C_WHITE, linewidth=2)
    )
    # Centre label
    ax.text(0,  0.08, str(results['rel_total']),
            ha='center', va='center', fontsize=26,
            fontweight='bold', color=C_DARK)
    ax.text(0, -0.22, 'total\nrelationships',
            ha='center', va='center', fontsize=8.5, color=C_GRAY)

    # Custom legend below donut
    for i, (col, lbl) in enumerate(zip(colors, labels)):
        y_off = -1.55 - i * 0.38
        ax.add_patch(plt.Rectangle(
            (-0.18, y_off - 0.10), 0.12, 0.22,
            color=col, transform=ax.transData, zorder=3
        ))
        ax.text(0.02, y_off + 0.01, lbl,
                ha='left', va='center', fontsize=8,
                color=C_DARK, transform=ax.transData)

    ax.set_ylim(-2.4, 1.4)
    ax.set_title(
        f"GUID state across all\n{results['rel_total']} asset relationships",
        fontsize=10, fontweight='bold', color=C_DARK, pad=10
    )
    ax.axis('off')