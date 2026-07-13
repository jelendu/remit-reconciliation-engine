"""Shared UI toolkit for the Remit Reconciliation Engine app.

Palette (validated dataviz reference set), CSS, cached data access against the
bundled DuckDB warehouse, and dbt-artifact parsing for the Pipeline page.
"""

from __future__ import annotations

import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "warehouse" / "raw.duckdb"
ARTIFACTS = ROOT / "dbt_project" / "artifacts"
REPO_URL = "https://github.com/jelendu/remit-reconciliation-engine"

# ---- palette --------------------------------------------------------------
# Chrome: Claude-inspired warm tan surfaces + terracotta accent.
# Data ink: the validated dataviz series blue and reserved status colors —
# kept distinct from brand chrome on purpose.
CLAUDE, CLAUDE_DEEP = "#D97757", "#B4552D"       # terracotta accent / deep (white text safe)
BLUE, BLUE_DARK = "#2a78d6", "#1c5cab"           # data series
RED_DIVERGING = "#e34948"
GOOD, GOOD_TEXT, GOOD_TINT = "#0ca30c", "#006300", "#e5f3e5"
CRIT, CRIT_TINT = "#d03b3b", "#fbe7e7"
WARN_TINT = "#FAE8B8"
INK, INK2, MUTED = "#201A15", "#5A5147", "#8E8272"
GRID, AXIS, SURFACE2 = "#E2D5C2", "#C6B69F", "#EFE3D3"

CHECK = {True: "✅", False: "❌"}

CSS = f"""
<style>
/* hero */
.rre-hero h1 {{ font-size: 2.6rem; line-height: 1.15; margin-bottom: .4rem; }}
.rre-hero p.lead {{ font-size: 1.15rem; color: {INK2}; max-width: 52rem; }}
/* pill badges */
.rre-badge {{
  display: inline-flex; align-items: center; gap: .4rem;
  border: 1px solid {GRID}; border-radius: 999px;
  padding: .15rem .7rem; font-size: .8rem; color: {INK2};
  background: #FBF6EE; margin-right: .4rem; white-space: nowrap;
}}
.rre-badge .dot {{
  width: .55rem; height: .55rem; border-radius: 50%;
  background: {GOOD}; display: inline-block;
  animation: rre-pulse 2s ease-in-out infinite;
}}
@keyframes rre-pulse {{ 50% {{ opacity: .35; }} }}
/* numbered steps */
.rre-step {{ display: flex; gap: .8rem; margin: .65rem 0; align-items: flex-start; }}
.rre-step .n {{
  flex: 0 0 1.7rem; height: 1.7rem; border-radius: 50%;
  background: {CLAUDE_DEEP}; color: #fff; font-weight: 700;
  display: flex; align-items: center; justify-content: center; font-size: .95rem;
}}
.rre-step .t b {{ display: block; }}
.rre-step .t span {{ color: {INK2}; font-size: .92rem; }}
/* status chips */
.rre-chip {{
  display: inline-block; padding: .1rem .6rem; border-radius: 6px;
  font-weight: 700; font-size: .9rem;
}}
.rre-chip.green {{ background: {GOOD_TINT}; color: {GOOD_TEXT}; }}
.rre-chip.red   {{ background: {CRIT_TINT}; color: {CRIT}; }}
.rre-chip.amber {{ background: {WARN_TINT}; color: #7a5c00; }}
/* math lines on the workbench */
.rre-math {{
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  background: {SURFACE2}; border: 1px solid {GRID}; border-radius: 8px;
  padding: .55rem .8rem; margin: .3rem 0 .6rem 0; font-size: .95rem; color: {INK};
}}
.rre-math .ok  {{ color: {GOOD_TEXT}; font-weight: 700; }}
.rre-math .bad {{ color: {CRIT}; font-weight: 700; }}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def live_badge() -> str:
    return ('<span class="rre-badge"><span class="dot"></span>'
            'LIVE — new synthetic remit cycle every 30 min via GitHub Actions</span>')


# ---- data access ----------------------------------------------------------
@st.cache_data(show_spinner=False)
def _q(sql: str, mtime: float) -> pd.DataFrame:
    # mtime is hashed on purpose: it busts the cache when dbt rebuilds the file
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        return con.execute(sql).df()
    finally:
        con.close()


def query(sql: str) -> pd.DataFrame:
    return _q(sql, DB_PATH.stat().st_mtime)


def cycles() -> pd.DataFrame:
    return query("""
        SELECT batch_id,
               min(remit_date)                                        AS cycle_date,
               count(*)                                               AS accounts,
               count(*) FILTER (status = 'GREEN')                     AS green,
               count(*) FILTER (status = 'RED')                       AS red,
               count(*) FILTER (needs_manual_review)                  AS manual_review,
               round(100.0 * count(*) FILTER (status = 'GREEN') / count(*), 1)
                                                                      AS match_rate_pct,
               sum(CASE WHEN abs(computed_rc_difference) > 0.01
                        THEN abs(computed_rc_difference) ELSE 0 END)  AS open_rc,
               sum(total_zeroed_rows)                                 AS zeroed_rows
        FROM marts.fct_reconciliation
        GROUP BY 1 ORDER BY 1
    """)


def export(batch_id: str) -> pd.DataFrame:
    return query(f"""
        SELECT * FROM marts.recon_export
        WHERE batch_id = '{batch_id}'
        ORDER BY status DESC, account_id
    """)


def freshness() -> str:
    return str(query("SELECT max(generated_at) AS ts FROM raw.raw.payments")["ts"].iloc[0])


def latest_batch() -> str:
    return str(cycles()["batch_id"].iloc[-1])


# ---- charts ---------------------------------------------------------------
def themed(chart: alt.Chart) -> alt.Chart:
    return (chart
            .configure_view(strokeOpacity=0)
            .configure_axis(gridColor=GRID, domainColor=AXIS, tickColor=AXIS,
                            labelColor=INK2, titleColor=INK2,
                            labelFontSize=12, titleFontSize=12)
            .configure_legend(labelColor=INK2, titleColor=INK2))


# ---- styled export table --------------------------------------------------
DISPLAY_COLS = {
    "account_id": "Account",
    "customer_name": "Customer",
    "status_display": "Status",
    "payment_check_passed": "Σ Pay = Remit",
    "charge_check_passed": "Σ Chg = CustChg",
    "adjustment_check_passed": "Σ Adj = Adjust",
    "rc_check_passed": "R-C ties",
    "remit_amount": "Remit $",
    "computed_rc_difference": "R-C computed",
    "reported_rc_difference": "R-C reported",
    "notes": "Notes",
    "sox_adjustment_note": "SOX adjustment note",
    "approval_status": "Approval",
}


def show_export(df: pd.DataFrame, height: int = 420) -> None:
    if df.empty:
        st.info("No accounts in this bucket for the selected cycle.")
        return
    df = df.assign(status_display=df["status"].map(
        {"GREEN": "🟢 GREEN", "RED": "🔴 RED"}))
    view = df[list(DISPLAY_COLS)].rename(columns=DISPLAY_COLS)
    for col in ["Σ Pay = Remit", "Σ Chg = CustChg", "Σ Adj = Adjust", "R-C ties"]:
        view[col] = view[col].map(CHECK)

    def row_style(row):
        tint = GOOD_TINT if "GREEN" in row["Status"] else CRIT_TINT
        return [f"background-color: {tint}; color: {INK}"] * len(row)

    def status_style(v):
        color = GOOD_TEXT if "GREEN" in v else CRIT
        return f"color: {color}; font-weight: 700"

    st.dataframe(
        view.style.apply(row_style, axis=1)
            .map(status_style, subset=["Status"])
            .format({"Remit $": "${:,.2f}", "R-C computed": "${:,.2f}",
                     "R-C reported": "${:,.2f}"}),
        width="stretch", hide_index=True, height=height)


# ---- dbt artifacts --------------------------------------------------------
@st.cache_data(show_spinner=False)
def dbt_artifacts(mtime: float) -> tuple[dict, dict]:
    manifest = json.loads((ARTIFACTS / "manifest.json").read_text(encoding="utf-8"))
    run_results = json.loads((ARTIFACTS / "run_results.json").read_text(encoding="utf-8"))
    return manifest, run_results


def load_dbt() -> tuple[dict, dict] | None:
    try:
        return dbt_artifacts((ARTIFACTS / "run_results.json").stat().st_mtime)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


LAYER_FILL = {"source": "#efeee9", "staging": "#cde2fb",
              "intermediate": "#9ec5f4", "marts": "#5598e7"}
LAYER_FONT = {"source": INK, "staging": INK, "intermediate": INK, "marts": "#ffffff"}


def _layer(unique_id: str, manifest: dict) -> str:
    if unique_id.startswith("source."):
        return "source"
    node = manifest["nodes"].get(unique_id, {})
    path = node.get("path", "") or ""
    for layer in ("staging", "intermediate", "marts"):
        if layer in path:
            return layer
    return "marts"


def lineage_dot(manifest: dict) -> str:
    """Graphviz DAG of sources + models, colored by layer, left-to-right."""
    keep: dict[str, str] = {}
    for uid in manifest.get("sources", {}):
        keep[uid] = manifest["sources"][uid]["name"]
    for uid, node in manifest["nodes"].items():
        if node.get("resource_type") == "model":
            keep[uid] = node["name"]

    lines = [
        "digraph dbt {",
        'rankdir=LR; bgcolor="transparent";',
        'graph [pad="0.2", nodesep="0.18", ranksep="0.9"];',
        'node [shape=box, style="rounded,filled", fontname="Segoe UI",'
        ' fontsize=11, penwidth=0, margin="0.14,0.08"];',
        f'edge [color="{AXIS}", arrowsize=0.6, penwidth=1.1];',
    ]
    for uid, name in keep.items():
        layer = _layer(uid, manifest)
        lines.append(
            f'"{name}" [fillcolor="{LAYER_FILL[layer]}",'
            f' fontcolor="{LAYER_FONT[layer]}"];')
    for uid, parents in manifest.get("parent_map", {}).items():
        if uid not in keep:
            continue
        for p in parents:
            if p in keep:
                lines.append(f'"{keep[p]}" -> "{keep[uid]}";')
    lines.append("}")
    return "\n".join(lines)


def test_results(manifest: dict, run_results: dict) -> pd.DataFrame:
    rows = []
    for r in run_results.get("results", []):
        uid = r.get("unique_id", "")
        if not uid.startswith("test."):
            continue
        node = manifest["nodes"].get(uid, {})
        rows.append({
            "test": node.get("name", uid),
            "kind": "singular" if node.get("test_metadata") is None else
                    node.get("test_metadata", {}).get("name", "generic"),
            "status": r.get("status", "").upper(),
            "time (s)": round(r.get("execution_time", 0.0), 2),
        })
    return pd.DataFrame(rows).sort_values(
        ["status", "kind", "test"]).reset_index(drop=True)


def model_timings(manifest: dict, run_results: dict) -> pd.DataFrame:
    rows = []
    for r in run_results.get("results", []):
        uid = r.get("unique_id", "")
        if not uid.startswith("model."):
            continue
        node = manifest["nodes"].get(uid, {})
        rows.append({
            "model": node.get("name", uid),
            "layer": _layer(uid, manifest),
            "materialized": node.get("config", {}).get("materialized", ""),
            "status": r.get("status", "").upper(),
            "time (s)": round(r.get("execution_time", 0.0), 2),
        })
    order = {"staging": 0, "intermediate": 1, "marts": 2}
    return (pd.DataFrame(rows)
            .assign(_o=lambda d: d["layer"].map(order))
            .sort_values(["_o", "model"]).drop(columns="_o")
            .reset_index(drop=True))


# ---- GitHub live feed -----------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def recent_commits() -> pd.DataFrame | None:
    try:
        import requests
        r = requests.get(
            "https://api.github.com/repos/jelendu/remit-reconciliation-engine/commits",
            params={"per_page": 10}, timeout=5)
        r.raise_for_status()
        rows = [{
            "when (UTC)": c["commit"]["author"]["date"].replace("T", " ").rstrip("Z"),
            "author": c["commit"]["author"]["name"],
            "message": c["commit"]["message"].split("\n")[0],
        } for c in r.json()]
        return pd.DataFrame(rows)
    except Exception:
        return None
