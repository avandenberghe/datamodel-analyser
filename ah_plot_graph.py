"""
ah_plot_graph.py — Asset Hub ID Analysis
==========================================
Graphic 2: Property graph by System of Record.
Intended for mail 3 (data analysis findings for architects).

Node layout is manually positioned — the three bands reflect the
natural domain clusters identified by connectivity analysis:
  - Organisational (top)  : WorkCenter, ServiceCenter
  - InfraRef     (middle) : location hubs + equipment assets (GUID ✓)
  - Trangis      (bottom) : network/linear assets — all without GUID
                            Oracle VIEW_* — non-alterable, Trangis in decom
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from ah_loader import DPI

# ── Palette ───────────────────────────────────────────────────────────────────
C_WHITE    = '#FFFFFF'
C_DARK     = '#1C2833'
C_GRAY     = '#566573'
C_BORD     = '#BDC3C7'
C_IR_DARK  = '#0B5345'   # InfraRef equipment nodes
C_IR_MID   = '#1A7A5E'
C_IR_LIGHT = '#D5F5E3'
C_TR_DARK  = '#154360'   # Trangis nodes
C_TR_MID   = '#1F618D'
C_TR_LIGHT = '#D6EAF8'
C_HUB_D    = '#7B241C'   # Location/topology hubs (high in-degree)
C_HUB_M    = '#C0392B'
C_ORG_D    = '#2C3E50'   # Organisational
C_AMBER    = '#D35400'   # Dual-source (GeographicalSite)
C_PURPLE   = '#6C3483'   # InfraRef exceptions (no GUID)
C_RED      = '#C0392B'


def plot_property_graph(out_path: str):
    """Render the property graph and save to out_path."""
    fig, ax = plt.subplots(figsize=(13, 9))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 9)
    ax.axis('off')
    fig.patch.set_facecolor(C_WHITE)

    # ── Internal drawing helpers ──────────────────────────────────────────────

    def band(y, h, label, color):
        """Shaded SoR band with italic label."""
        ax.add_patch(FancyBboxPatch(
            (0.3, y), 12.4, h,
            boxstyle='round,pad=0.05',
            facecolor=color, edgecolor=color,
            linewidth=1.2, alpha=0.07, zorder=1
        ))
        ax.text(0.55, y + h - 0.18, label,
                fontsize=7, color=color,
                fontweight='bold', style='italic', alpha=0.9, zorder=2)

    def node(x, y, w, h, label, sublabel, fill, border,
             textcol='#FFFFFF', badge=False):
        """Rounded-rect node with optional warning badge."""
        ax.add_patch(FancyBboxPatch(
            (x, y), w, h,
            boxstyle='round,pad=0.05',
            facecolor=fill, edgecolor=border,
            linewidth=1.2, zorder=3
        ))
        ty = y + h / 2 + (0.10 if sublabel else 0)
        ax.text(x + w / 2, ty, label,
                ha='center', va='center',
                fontsize=7.5, fontweight='bold', color=textcol, zorder=4)
        if sublabel:
            ax.text(x + w / 2, y + h / 2 - 0.14, sublabel,
                    ha='center', va='center',
                    fontsize=5.8, color=textcol, alpha=0.82, zorder=4)
        if badge:
            bx, by = x + w - 0.01, y + h - 0.01
            ax.add_patch(FancyBboxPatch(
                (bx - 0.28, by - 0.20), 0.28, 0.20,
                boxstyle='round,pad=0.02',
                facecolor=C_RED, edgecolor='none', zorder=5
            ))
            ax.text(bx - 0.14, by - 0.10, '⚠',
                    ha='center', va='center',
                    fontsize=5.5, fontweight='bold', color='white', zorder=6)

    def arr(x1, y1, x2, y2, col, lw=0.9, dashed=False, thick=False):
        """Arrow between two points."""
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(
                        arrowstyle='->', color=col,
                        lw=1.6 if thick else lw,
                        linestyle=(0, (4, 3)) if dashed else 'solid',
                        connectionstyle='arc3,rad=0.0'
                    ), zorder=2)

    # ── Title ─────────────────────────────────────────────────────────────────
    ax.text(6.5, 8.72,
            'Asset Hub — Property Graph by System of Record',
            ha='center', va='center', fontsize=13,
            fontweight='bold', color=C_DARK)
    ax.text(6.5, 8.42,
            'Node: Concept  ·  SoR.Table  ·  GUID ✓/✗  ·  [in-degree]',
            ha='center', va='center', fontsize=7.5,
            color=C_GRAY, style='italic')

    # ── SoR bands ─────────────────────────────────────────────────────────────
    band(7.65, 0.60, 'SAP PM / Organisational', C_ORG_D)
    band(4.00, 3.55, 'InfraRef  (MSSQL staging — GUID available)', C_IR_MID)
    band(0.20, 3.65,
         'Trangis  (Oracle VIEW_* — read-only, non-alterable, in decom — NO GUID)',
         C_TR_MID)

    # ── Organisational nodes ──────────────────────────────────────────────────
    node(0.55, 7.70, 2.4, 0.46,
         'WorkCenter', 'SAP · WorkCenterGUID · GUID ✓ · [44]',
         C_ORG_D, C_ORG_D)
    node(3.30, 7.70, 3.2, 0.46,
         'ServiceCenter', 'InfraRef.ServiceCenter · SystemID · GUID ✓ · [53]',
         C_ORG_D, C_ORG_D)

    # ── InfraRef location hubs (high in-degree, some non-unique) ─────────────
    node(0.55, 6.80, 3.3, 0.50,
         'GeographicalSubstation',
         'InfraRef.GeographicalSubstation · LocationGUID · [42]',
         C_HUB_D, C_HUB_M)
    node(4.15, 6.80, 2.8, 0.50,
         'GeographicalBay',
         'InfraRef.GeographicalBay · id ⚠ NON-UNIQUE · [40]',
         C_HUB_D, C_RED, badge=True)
    node(7.25, 6.80, 3.1, 0.50,
         'PowerTransformerPlace',
         'InfraRef.TransformerPlace · id ⚠ NON-UNIQUE · [40]',
         C_HUB_D, C_RED, badge=True)
    node(0.55, 5.95, 2.8, 0.50,
         'GeographicalContainer',
         'InfraRef.PUC · LocationGUID · [30]',
         C_HUB_D, C_HUB_M)

    # ── InfraRef equipment (representative sample) ────────────────────────────
    node(4.15, 5.95, 2.6, 0.50,
         'PowerTransformerAsset',
         'InfraRef.PowerTransformer · GUID ✓ · [4]',
         C_IR_DARK, C_IR_MID)
    node(7.05, 5.95, 2.5, 0.50,
         'CircuitBreakerAsset',
         'InfraRef.CircuitBreaker · GUID ✓ · [2]',
         C_IR_DARK, C_IR_MID)
    node(9.80, 5.95, 2.55, 0.50,
         'HighVoltageTerminal',
         'InfraRef.HighVoltageTerminal · GUID ✓ · [2]',
         C_IR_DARK, C_IR_MID)

    # Collapsed band — remaining 40 InfraRef equipment assets
    ax.add_patch(FancyBboxPatch(
        (0.55, 4.85), 11.80, 0.46,
        boxstyle='round,pad=0.05',
        facecolor=C_IR_LIGHT, edgecolor=C_IR_MID,
        linewidth=0.8, linestyle=(0, (4, 3)), zorder=3
    ))
    ax.text(6.5, 5.075,
            '+ 40 more InfraRef equipment assets  '
            '(all GUID ✓, out-degree 5–7, linking to hubs above)',
            ha='center', va='center', fontsize=7.5,
            color=C_IR_DARK, style='italic', zorder=4)

    # ── InfraRef exceptions (no GUID despite being InfraRef-sourced) ──────────
    node(0.55, 4.12, 2.5, 0.46,
         'FaultRecorderAsset', 'InfraRef.FaultAnalysis · no GUID',
         C_PURPLE, C_PURPLE, textcol='#E8DAEF')
    node(3.35, 4.12, 2.0, 0.46,
         'SubStation', 'InfraRef.FunctionalSite · no GUID',
         C_PURPLE, C_PURPLE, textcol='#E8DAEF')
    node(5.60, 4.12, 2.1, 0.46,
         'VoltageLevel', 'InfraRef.FunctionalStation · no GUID',
         C_PURPLE, C_PURPLE, textcol='#E8DAEF')

    # ── Trangis nodes ─────────────────────────────────────────────────────────
    node(0.55, 3.04, 2.6, 0.50,
         'Junction', 'VIEW_JUNCTION · no GUID · [9] in · [13] out',
         C_TR_DARK, C_TR_MID)
    node(3.45, 3.04, 1.9, 0.50,
         'Tower', 'VIEW_SUPPORT · no GUID · [3] in · [9] out',
         C_TR_DARK, C_TR_MID)
    node(5.60, 3.04, 2.2, 0.50,
         'Line', 'VIEW_CIRCUIT · id ⚠ NON-UNIQUE · [11]',
         C_TR_DARK, C_RED, badge=True)
    node(8.05, 3.04, 2.55, 0.50,
         'GeographicalSpan',
         'VIEW_GEOSPAN · no GUID · [4] in · [7] out',
         C_TR_DARK, C_TR_MID)

    # GeographicalSite — dual-source (amber)
    node(0.55, 2.16, 3.0, 0.50,
         'GeographicalSite',
         'VIEW_SITE / InfraRef.GeographicalSite · DUAL SOURCE · no master · [11]',
         C_AMBER, C_AMBER)
    node(3.85, 2.16, 2.6, 0.50,
         'AerialConductorSetSpan',
         'VIEW_ELECTRICAL_SPAN · no GUID · [3]',
         C_TR_DARK, C_TR_MID)
    node(6.70, 2.16, 2.9, 0.50,
         'UndergroundConductorSetSpan',
         'VIEW_UNDERGROUND_CABLE · no GUID · [2]',
         C_TR_DARK, C_TR_MID)
    node(9.85, 2.16, 2.50, 0.50,
         'GuardCircuit',
         'VIEW_GUARD_CIRCUIT · id ⚠ NON-UNIQUE',
         C_TR_DARK, C_RED, badge=True)

    # Collapsed band — remaining Trangis assets
    ax.add_patch(FancyBboxPatch(
        (0.55, 0.92), 11.80, 0.46,
        boxstyle='round,pad=0.05',
        facecolor=C_TR_LIGHT, edgecolor=C_TR_MID,
        linewidth=0.8, linestyle=(0, (4, 3)), zorder=3
    ))
    ax.text(6.5, 1.15,
            '+ 20 more Trangis assets  '
            '(Building, Door, Fence, Roof, Room, Parcel, EarthWireSpan, '
            'ConductorSetHook, TelecomCable…  all no GUID)',
            ha='center', va='center', fontsize=7.5,
            color=C_TR_DARK, style='italic', zorder=4)

    # ── Shadow key annotation ─────────────────────────────────────────────────
    ax.add_patch(FancyBboxPatch(
        (0.55, 0.28), 11.80, 0.38,
        boxstyle='round,pad=0.04',
        facecolor='#FEF9E7', edgecolor=C_AMBER,
        linewidth=0.9, linestyle=(0, (3, 2)), zorder=3
    ))
    ax.text(0.80, 0.47, '⚠ Shadow key:',
            ha='left', va='center', fontsize=7,
            fontweight='bold', color=C_AMBER, zorder=4)
    ax.text(2.30, 0.47,
            'IncidentNumber referenced in 44 comment annotations as informal '
            'fallback correlation key — outside the formal id/identifier model.  '
            'MongoDB _id not surfaced on output port.',
            ha='left', va='center', fontsize=6.8, color=C_GRAY, zorder=4)

    # ── Key relationships ─────────────────────────────────────────────────────
    # Equipment → location hubs
    arr(4.15, 6.20, 3.85, 7.08, C_HUB_M, lw=0.8)
    arr(4.15, 6.20, 1.90, 7.08, C_HUB_M, lw=0.8)
    arr(7.05, 6.20, 7.55, 7.08, C_HUB_M, lw=0.8)
    arr(4.15, 6.20, 1.90, 6.48, C_HUB_M, lw=0.8)
    # Equipment → organisational
    arr(4.45, 5.95, 1.75, 8.16, C_ORG_D, lw=0.6, dashed=True)
    arr(5.45, 5.95, 4.90, 8.16, C_ORG_D, lw=0.6, dashed=True)
    # Hub ↔ hub
    arr(3.85, 7.06, 4.15, 7.06, C_HUB_M, lw=0.8)
    arr(4.15, 6.92, 3.85, 6.92, C_HUB_M, lw=0.8)
    arr(3.85, 6.92, 7.25, 6.92, C_HUB_M, lw=0.7)
    arr(1.90, 6.80, 1.90, 6.48, C_HUB_M, lw=0.8)
    # Cross-boundary InfraRef → Trangis (GUID lost)
    arr(1.90, 4.00, 2.05, 2.66, C_RED, lw=0.9, dashed=True)
    ax.text(0.60, 3.38, 'cross-boundary\n(GUID lost)',
            fontsize=5.8, color=C_RED, style='italic', ha='left')
    arr(10.20, 5.95, 1.85, 3.54, C_RED, lw=0.9, dashed=True)
    # Trangis topology (To-Many = thick)
    arr(5.60, 3.29, 5.60, 3.54, C_TR_MID, lw=1.8, thick=True)
    arr(3.15, 3.29, 8.30, 3.54, C_TR_MID, lw=1.8, thick=True)
    arr(3.45, 3.29, 3.15, 3.54, C_TR_MID, lw=1.8, thick=True)
    arr(4.40, 3.04, 5.65, 3.04, C_TR_MID, lw=1.5, thick=True)
    arr(4.85, 2.66, 1.85, 3.04, C_TR_MID, lw=0.9)
    arr(0.80, 0.92, 1.40, 2.16, C_TR_MID, lw=0.8)
    arr(10.35, 2.16, 10.35, 0.92, C_TR_MID, lw=0.8)

    # ── Legend ────────────────────────────────────────────────────────────────
    lx, ly = 10.20, 4.85
    legend_items = [
        (C_HUB_D,   C_HUB_M,  'Location/topology hub'),
        (C_IR_DARK, C_IR_MID, 'InfraRef equipment (GUID ✓)'),
        (C_TR_DARK, C_TR_MID, 'Trangis asset (no GUID)'),
        (C_PURPLE,  C_PURPLE, 'InfraRef exception (no GUID)'),
        (C_AMBER,   C_AMBER,  'Dual-source / no master'),
        (C_ORG_D,   C_ORG_D,  'Organisational'),
    ]
    ax.add_patch(FancyBboxPatch(
        (lx - 0.10, ly - 7.4 * 0.28), 2.75, 7.7 * 0.28 + 0.22,
        boxstyle='round,pad=0.05',
        facecolor='#FAFAFA', edgecolor=C_BORD,
        linewidth=0.7, zorder=4
    ))
    for i, (fill, border, label) in enumerate(legend_items):
        yy = ly - i * 0.28
        ax.add_patch(FancyBboxPatch(
            (lx, yy - 0.09), 0.22, 0.18,
            boxstyle='round,pad=0.02',
            facecolor=fill, edgecolor=border,
            linewidth=0.8, zorder=5
        ))
        ax.text(lx + 0.30, yy, label,
                va='center', fontsize=6.3, color=C_DARK, zorder=5)
    ax.plot([lx, lx + 0.22], [ly - 6 * 0.28 + 0.05] * 2,
            color=C_RED, lw=1.8, zorder=5)
    ax.text(lx + 0.30, ly - 6 * 0.28 + 0.05,
            'To-Many relationship', va='center', fontsize=6.3, color=C_DARK)
    ax.plot([lx, lx + 0.22], [ly - 7 * 0.28 + 0.05] * 2,
            color=C_RED, lw=0.9, linestyle=(0, (4, 3)), zorder=5)
    ax.text(lx + 0.30, ly - 7 * 0.28 + 0.05,
            'Cross-boundary (GUID lost)', va='center', fontsize=6.3, color=C_DARK)
    ax.text(lx + 1.25, ly - 7.5 * 0.28 + 0.10,
            '[ n ] = in-degree',
            ha='center', va='center', fontsize=6,
            color=C_GRAY, style='italic', zorder=5)

    plt.tight_layout(pad=0.2)
    plt.savefig(out_path, dpi=DPI, bbox_inches='tight', facecolor=C_WHITE)
    plt.close()
    print(f"  ✓  {out_path}")