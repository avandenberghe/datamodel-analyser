"""
ah_narrative.py — LLM-powered narrative generation
====================================================
- Calls the Claude API to produce a human-readable report from the
  raw analysis numbers, architectural context, and (optionally)
  changes since the previous run (stored in the DuckDB database)
- The system prompt is loaded from prompts/system_prompt.txt —
  it is a strategic asset maintained separately from code
- Falls back to a structured plain-text report if no API key is set
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import pandas as pd
from dotenv import load_dotenv

load_dotenv()


MODEL      = "claude-sonnet-4-20250514"
PROMPT_DIR = Path(__file__).parent / "prompts"


def _load_system_prompt() -> str:
    """Load the system prompt from prompts/system_prompt.txt."""
    path = PROMPT_DIR / "system_prompt.txt"
    if not path.exists():
        raise FileNotFoundError(
            f"System prompt not found at {path}. "
            "See SPEC.md section 8 for requirements."
        )
    return path.read_text().strip()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _serialise_results(results: dict) -> dict:
    """Convert a results dict (may contain DataFrames) to JSON-safe form."""
    out = {}
    for k, v in results.items():
        if isinstance(v, pd.DataFrame):
            out[k] = v.to_dict("records")
        else:
            out[k] = v
    return out




# ── Prompt construction ─────────────────────────────────────────────────────

def _build_user_prompt(results: dict, source_file: str,
                       previous: dict | None) -> str:
    """Build the user-turn prompt with all the numbers."""
    parts = [
        f"Source file analysed: {source_file}",
        f"Analysis timestamp: {datetime.now(timezone.utc).isoformat()}",
        "",
        "=== CURRENT RUN — RAW NUMBERS ===",
        json.dumps(_serialise_results(results), indent=2, default=str),
    ]

    if previous:
        parts += [
            "",
            f"=== PREVIOUS RUN (#{previous['run_id']}, {previous['timestamp']}) ===",
            f"Previous source file: {previous['source_file']}",
        ]
        if "results" in previous:
            parts.append(
                json.dumps(previous["results"], indent=2, default=str)
            )
        parts += [
            "",
            "Please include a section comparing the current run to the",
            "previous run, highlighting what changed and whether the",
            "situation improved or degraded.",
        ]
    else:
        parts += [
            "",
            "No previous run available — this is the first analysis.",
        ]

    parts += [
        "",
        "The outputs include a data-driven concept relationship graph "
        "(graph.png) built from the concepts and relationships tables. "
        "Please include a section interpreting the graph structure: "
        "what the topology reveals about the data architecture — hub nodes, "
        "clustering by source system, fan-out patterns, isolated subgraphs, "
        "and what the red-bordered nodes (data quality issues) mean for the "
        "overall system's ability to resolve cross-references.",
        "",
        "Please write the full analysis report now.",
    ]
    return "\n".join(parts)


# ── Public API ───────────────────────────────────────────────────────────────

def generate_narrative(results: dict, source_file: str,
                       previous: dict | None = None) -> str:
    """
    Generate a human-readable report.

    - If ANTHROPIC_API_KEY is set, calls the Claude API.
    - Otherwise returns a structured fallback.

    Parameters
    ----------
    results     : current run's analysis results dict
    source_file : name of the imported Excel file
    previous    : previous run metadata from ah_loader.get_previous_run(),
                  or None if this is the first run
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return _fallback_summary(
            results, source_file, previous,
            reason="No ANTHROPIC_API_KEY set — using structured fallback."
        )

    try:
        system_prompt = _load_system_prompt()
        client = anthropic.Anthropic(api_key=api_key)
        user_prompt = _build_user_prompt(results, source_file, previous)

        message = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return message.content[0].text

    except anthropic.APIError as e:
        print(f"  ⚠  Claude API error: {e}")
        return _fallback_summary(
            results, source_file, previous,
            reason=f"Claude API unavailable ({e}). Using structured fallback."
        )


def _fallback_summary(results: dict, source_file: str,
                      previous: dict | None, reason: str = "") -> str:
    """Structured markdown fallback when the Claude API is not available."""
    r = results
    ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

    ir_total = r['infraref_total']
    ir_yes   = r['infraref_guid_yes']
    ir_no    = r['infraref_guid_no']
    ir_pct   = r['infraref_guid_pct']
    tr_total = r['trangis_total']
    tr_yes   = r['trangis_guid_yes']
    tr_no    = r['trangis_guid_no']
    total    = ir_total + tr_total

    lines = [
        '# Asset Hub — Data Structure Analysis Report',
        '',
        f'**Source file:** {source_file}',
        f'**Generated:** {ts}',
        '',
    ]
    if reason:
        lines += [f'> {reason}', '']

    lines += [
        '## 1. GUID Coverage by Source System',
        '',
        '| System | With GUID | Without GUID | Total | Coverage |',
        '|--------|-----------|-------------|-------|----------|',
        f'| InfraRef | {ir_yes} | {ir_no} | {ir_total} | {ir_pct}% |',
        f'| Trangis | {tr_yes} | {tr_no} | {tr_total} | 0% |',
        '',
    ]

    nu = r['non_unique_count']
    lines += ['## 2. Non-Unique IDs — Key-Value Invariant Violations', '']
    if nu == 0:
        lines.append('No violations found.')
    else:
        lines += [
            f'{nu} of {total} concepts have non-unique IDs:',
            '',
            '| Concept | Source | Table |',
            '|---------|--------|-------|',
        ]
        for c in r['non_unique_concepts']:
            lines.append(f"| {c['concept']} | {c['sor']} | {c['sor_table']} |")
    lines.append('')

    dual = r['dual_source_concepts']
    lines += ['## 3. Dual-Source Mastery Ambiguity', '']
    if not dual:
        lines.append('No ambiguity found.')
    else:
        for c in dual:
            lines.append(f'- **{c}**')
    lines.append('')

    lines += [
        '## 4. Missing GUIDs — Concepts Without a Key',
        '',
        f'| Metric | Count |',
        f'|--------|------:|',
        f'| Total without GUID | {r["no_guid_total"]} of {total} |',
        f'| Trangis | {r["no_guid_trangis"]} |',
        f'| InfraRef | {r["no_guid_infraref"]} |',
        '',
    ]
    if r['no_guid_infraref_names']:
        lines.append(
            'InfraRef exceptions: '
            + ', '.join(r['no_guid_infraref_names'])
        )
        lines.append('')

    lines += [
        '## 5. Relationship-Level GUID Resolution',
        '',
        '| Metric | Count | % |',
        '|--------|------:|--:|',
        f'| Total relationships | {r["rel_total"]} | |',
        f'| GUID in source | {r["rel_avail"]} | |',
        f'| Fetched by Asset Hub | {r["rel_fetched"]} | |',
        f'| Unresolved | {r["rel_unresolved"]} | {r["rel_unresolved_pct"]}% |',
        '',
    ]

    lines += ['## 6. Comment Keyword Frequencies', '',
              '| Keyword | Mentions |',
              '|---------|--------:|']
    for kw, count in sorted(r['keyword_counts'].items(), key=lambda x: -x[1]):
        lines.append(f'| {kw} | {count} |')
    lines.append('')

    if previous:
        lines += [
            '## Previous Run',
            '',
            f'- **Timestamp:** {previous["timestamp"]}',
            f'- **Source file:** {previous["source_file"]}',
            '',
            '> Delta comparison requires LLM narrative — add API credits.',
            '',
        ]

    return "\n".join(lines)
