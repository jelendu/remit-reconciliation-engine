"""Remit Reconciliation Engine — Streamlit dashboard.

Reads the bundled DuckDB warehouse (warehouse/raw.duckdb) that dbt builds into.
All data is 100% synthetic and regenerated on a schedule by GitHub Actions.

Ships its own light theme (.streamlit/config.toml); every styled table cell
sets BOTH background and text color so rows stay readable everywhere.
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import duckdb
import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).resolve().parent.parent / "warehouse" / "raw.duckdb"

# Reference dataviz palette (validated set — see README/dataviz notes)
BLUE, BLUE_DARK = "#2a78d6", "#1c5cab"          # categorical slot 1
RED_DIVERGING = "#e34948"                        # diverging warm pole
GOOD, GOOD_TEXT, GOOD_TINT = "#0ca30c", "#006300", "#e5f3e5"
CRIT, CRIT_TINT = "#d03b3b", "#fbe7e7"
WARN_TINT = "#fdf3d7"
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"

CHECK = {True: "✅", False: "❌"}

st.set_page_config(page_title="Remit Reconciliation Engine",
                   page_icon="🧾", layout="wide")


@st.cache_data(show_spinner=False)
def q(sql: str, mtime: float) -> pd.DataFrame:
    """Query the warehouse read-only; cache busts when the file changes.

    `mtime` is part of the cache key on purpose — a leading underscore would
    make Streamlit skip it when hashing and the cache would never invalidate.
    """
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        return con.execute(sql).df()
    finally:
        con.close()


def query(sql: str) -> pd.DataFrame:
    return q(sql, DB_PATH.stat().st_mtime)


def themed(chart: alt.Chart) -> alt.Chart:
    return (chart
            .configure_view(strokeOpacity=0)
            .configure_axis(gridColor=GRID, domainColor=AXIS, tickColor=AXIS,
                            labelColor=INK2, titleColor=INK2,
                            labelFontSize=12, titleFontSize=12)
            .configure_legend(labelColor=INK2, titleColor=INK2))


def style_export(df: pd.DataFrame) -> "pd.io.formats.style.Styler":
    """Status-tinted rows. Text color is set explicitly alongside every
    background so the table is readable on any theme."""
    def row_style(row):
        tint = GOOD_TINT if "GREEN" in row["Status"] else CRIT_TINT
        return [f"background-color: {tint}; color: {INK}"] * len(row)

    def status_style(v):
        color = GOOD_TEXT if "GREEN" in v else CRIT
        return f"color: {color}; font-weight: 700"

    return (df.style
            .apply(row_style, axis=1)
            .map(status_style, subset=["Status"])
            .format({"Remit $": "${:,.2f}", "R-C computed": "${:,.2f}",
                     "R-C reported": "${:,.2f}"}))


# ---------------------------------------------------------------- header
st.title("🧾 Remit Reconciliation Engine")
st.caption(
    "Reconciles synthetic utility-billing payments against remittances — "
    "**SUM(Payment)=Remit · SUM(UtilityCharge)=CustCharge · "
    "SUM(AdjustmentAmt)=Adjustments · (CustCharge+Adjustments)−Remit = "
    "reported R-C**. Duplicate-inflated columns are repaired by zero-out "
    "dedupe; irreconcilable accounts go to manual review. All data is 100% "
    "synthetic; a GitHub Actions job appends a new remit cycle every 30 min."
)

if not DB_PATH.exists():
    st.error("warehouse/raw.duckdb not found — run the pipeline first "
             "(data_gen/generate.py → warehouse/load_raw.py → dbt build).")
    st.stop()

cycles = query("""
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
freshness = query("SELECT max(generated_at) AS ts FROM raw.raw.payments")["ts"].iloc[0]

with st.sidebar:
    st.header("Filters")
    batch_id = st.selectbox(
        "Remit cycle (batch)", cycles["batch_id"][::-1],
        format_func=lambda b: (
            f"{b} — {pd.Timestamp(cycles.set_index('batch_id').loc[b, 'cycle_date']).date()} "
            f"({cycles.set_index('batch_id').loc[b, 'accounts']} accounts)"),
    )
    st.caption(f"Latest synthetic batch generated **{freshness}** (UTC). "
               "A scheduled GitHub Action appends the next one every 30 min "
               "and redeploys this app.")
    st.divider()
    st.markdown(
        "**How to read this**\n\n"
        "🟢 **GREEN** — all four checks pass\n\n"
        "🔴 **RED** — at least one check failed\n\n"
        "**Zero-out dedupe** zeroes *duplicate* dollar amounts (never real "
        "ones) until detail ties to summary. Still unmatched afterwards → "
        "**manual review** plus a SOX-style adjustment note for manager "
        "approval."
    )
    st.divider()
    st.markdown(
        "**Pipeline** — Python generator → DuckDB → dbt "
        "(staging → intermediate → marts, 43 tests) → this app. "
        "[Source on GitHub](https://github.com/jelendu/remit-reconciliation-engine)"
    )

row = cycles.set_index("batch_id").loc[batch_id]
pos = cycles.index[cycles["batch_id"] == batch_id][0]
prev = cycles.iloc[pos - 1] if pos > 0 else None

# ---------------------------------------------------------------- KPIs
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Accounts in cycle", int(row["accounts"]),
          delta=None if prev is None else int(row["accounts"] - prev["accounts"]),
          delta_color="off")
c2.metric("Match rate", f"{row['match_rate_pct']:.1f}%",
          delta=None if prev is None else f"{row['match_rate_pct'] - prev['match_rate_pct']:+.1f} pp")
c3.metric("🟢 GREEN", int(row["green"]),
          delta=None if prev is None else int(row["green"] - prev["green"]))
c4.metric("🔴 RED", int(row["red"]),
          delta=None if prev is None else int(row["red"] - prev["red"]),
          delta_color="inverse")
c5.metric("Manual review", int(row["manual_review"]),
          delta=None if prev is None else int(row["manual_review"] - prev["manual_review"]),
          delta_color="inverse")
c6.metric("Open R-C differences", f"${row['open_rc']:,.2f}",
          delta=None if prev is None else f"{row['open_rc'] - prev['open_rc']:+,.2f}",
          delta_color="inverse")

export = query(f"""
    SELECT * FROM marts.recon_export
    WHERE batch_id = '{batch_id}'
    ORDER BY status DESC, account_id
""")

# ---------------------------------------------------------------- charts
left, right = st.columns((3, 2), gap="large")

with left:
    st.markdown("##### Match rate by remit cycle")
    base = alt.Chart(cycles).encode(
        x=alt.X("batch_id:N", title=None, axis=alt.Axis(labelAngle=0)))
    line = base.mark_line(color=BLUE, strokeWidth=2).encode(
        y=alt.Y("match_rate_pct:Q", title="match rate %",
                scale=alt.Scale(domain=[0, 100])))
    pts = base.mark_point(filled=True, size=80, color=BLUE).encode(
        y="match_rate_pct:Q",
        tooltip=[alt.Tooltip("batch_id", title="cycle"),
                 alt.Tooltip("accounts", title="accounts"),
                 alt.Tooltip("green", title="GREEN"),
                 alt.Tooltip("red", title="RED"),
                 alt.Tooltip("match_rate_pct", title="match rate %")])
    last_label = base.transform_filter(
        alt.datum.batch_id == str(cycles["batch_id"].iloc[-1])
    ).mark_text(dy=-14, color=BLUE_DARK, fontWeight="bold").encode(
        y="match_rate_pct:Q",
        text=alt.Text("match_rate_pct:Q", format=".1f"))
    st.altair_chart(themed((line + pts + last_label).properties(height=230)),
                    width="stretch")

with right:
    st.markdown(f"##### Failed checks — cycle {batch_id}")
    fails = pd.DataFrame({
        "check": ["Σ Payment = Remit", "Σ Charge = CustCharge",
                  "Σ Adjustment = Adjustments", "R-C ties to export"],
        "failed accounts": [
            int((~export["payment_check_passed"]).sum()),
            int((~export["charge_check_passed"]).sum()),
            int((~export["adjustment_check_passed"]).sum()),
            int((~export["rc_check_passed"]).sum()),
        ],
    })
    bars = alt.Chart(fails).mark_bar(
        color=BLUE, cornerRadiusEnd=4, height=20
    ).encode(
        x=alt.X("failed accounts:Q", title="accounts failing",
                axis=alt.Axis(format="d", tickMinStep=1)),
        y=alt.Y("check:N", title=None, sort=None),
        tooltip=["check", "failed accounts"])
    labels = bars.mark_text(align="left", dx=6, color=INK2).encode(
        text="failed accounts:Q")
    st.altair_chart(themed((bars + labels).properties(height=230)),
                    width="stretch")

# ---------------------------------------------------------------- tables
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


def show_export(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No accounts in this bucket for the selected cycle.")
        return
    df = df.assign(status_display=df["status"].map(
        {"GREEN": "🟢 GREEN", "RED": "🔴 RED"}))
    view = df[list(DISPLAY_COLS)].rename(columns=DISPLAY_COLS)
    for col in ["Σ Pay = Remit", "Σ Chg = CustChg", "Σ Adj = Adjust", "R-C ties"]:
        view[col] = view[col].map(CHECK)
    st.dataframe(style_export(view), width="stretch",
                 hide_index=True, height=420)


tab_all, tab_matched, tab_unmatched, tab_review, tab_sox, tab_drill = st.tabs(
    ["All accounts", "🟢 Matched", "🔴 Unmatched", "🔍 Manual review",
     "🗒️ SOX approval queue", "🔬 Account drill-down"])

with tab_all:
    show_export(export)
    st.download_button(
        "⬇️ Download export (CSV)",
        export.to_csv(index=False).encode(),
        file_name=f"recon_export_{batch_id}.csv", mime="text/csv")

with tab_matched:
    show_export(export[export["status"] == "GREEN"])

with tab_unmatched:
    show_export(export[export["status"] == "RED"])
    diffs = export.loc[export["computed_rc_difference"].abs() > 0.01,
                       ["account_id", "computed_rc_difference"]].copy()
    if not diffs.empty:
        st.markdown(f"##### Open R-C differences by account — cycle {batch_id}")
        diffs["direction"] = diffs["computed_rc_difference"].map(
            lambda v: "remit short (owed)" if v > 0 else "remit over")
        diffs = diffs.reindex(
            diffs["computed_rc_difference"].abs()
            .sort_values(ascending=False).index)[:12]
        bars = alt.Chart(diffs).mark_bar(cornerRadiusEnd=4, height=16).encode(
            x=alt.X("computed_rc_difference:Q", title="(CustCharge+Adjustments) − Remit, $"),
            y=alt.Y("account_id:N", title=None, sort=None),
            color=alt.Color("direction:N", title=None,
                            scale=alt.Scale(
                                domain=["remit short (owed)", "remit over"],
                                range=[RED_DIVERGING, BLUE])),
            tooltip=["account_id",
                     alt.Tooltip("computed_rc_difference", title="difference $",
                                 format="$,.2f")])
        st.altair_chart(themed(bars.properties(height=max(120, 24 * len(diffs)))),
                        width="stretch")

with tab_review:
    st.caption("A detail column could not be tied to its summary even after "
               "zeroing every eligible duplicate — a human has to look.")
    show_export(export[export["needs_manual_review"]])

with tab_sox:
    st.caption(f"{int(row['zeroed_rows'])} duplicate row(s) zeroed this cycle. "
               "Zero-out adjustments alter no real amounts and require "
               "manager sign-off.")
    show_export(export[export["sox_adjustment_note"].notna()])

with tab_drill:
    acct = st.selectbox("Account", export["account_id"], key="drill")
    hdr = export[export["account_id"] == acct].iloc[0]
    st.markdown(
        f"### {hdr['customer_name']} · {acct} · cycle {batch_id} — "
        f"{'🟢 GREEN' if hdr['status'] == 'GREEN' else '🔴 RED'}")
    st.markdown(f"_{hdr['notes']}_")
    if isinstance(hdr["sox_adjustment_note"], str):
        st.warning(hdr["sox_adjustment_note"], icon="🗒️")

    tie_outs = [
        ("Payments", "fct_payments", "payment_id",
         hdr["payment_adjusted_sum"], hdr["remit_amount"],
         hdr["payment_check_passed"], "remit"),
        ("Utility charges", "fct_utility_charges", "charge_id",
         hdr["charge_adjusted_sum"], hdr["cust_charge_amount"],
         hdr["charge_check_passed"], "CustCharge"),
        ("Adjustments", "fct_adjustments", "adjustment_id",
         hdr["adjustment_adjusted_sum"], hdr["adjustments_amount"],
         hdr["adjustment_check_passed"], "Adjustments summary"),
    ]
    for label, table, id_col, adjusted, target, passed, target_name in tie_outs:
        verdict = ("✅ ties out" if passed
                   else f"❌ off by ${abs(adjusted - target):,.2f}")
        st.markdown(
            f"**{label}** — detail (after zero-out) **${adjusted:,.2f}** vs "
            f"{target_name} **${target:,.2f}** → {verdict}")
        detail = query(f"""
            SELECT * FROM marts.{table}
            WHERE account_id = '{acct}' AND batch_id = '{batch_id}'
            ORDER BY {id_col}
        """)
        if detail.empty:
            st.caption("no detail rows this cycle")
            continue

        def zero_style(r):
            css = (f"background-color: {WARN_TINT}; color: {INK}"
                   if r["is_zeroed"] else f"color: {INK}")
            return [css] * len(r)

        st.dataframe(
            detail.style.apply(zero_style, axis=1).format(
                {"original_amount": "${:,.2f}", "adjusted_amount": "${:,.2f}"}),
            width="stretch", hide_index=True)

st.divider()
st.caption(
    "Synthetic demo — no real customer, company, or billing data. "
    "Pipeline: Python generator → DuckDB → dbt (staging/intermediate/marts, "
    "43 tests) → this dashboard, refreshed every 30 min by GitHub Actions. "
    "Source: [github.com/jelendu/remit-reconciliation-engine]"
    "(https://github.com/jelendu/remit-reconciliation-engine)")
