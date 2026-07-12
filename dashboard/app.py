"""Remit Reconciliation Engine — Streamlit dashboard.

Reads the bundled DuckDB warehouse (warehouse/raw.duckdb) that dbt builds into.
All data is 100% synthetic and regenerated on a schedule by GitHub Actions.
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import duckdb
import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).resolve().parent.parent / "warehouse" / "raw.duckdb"

st.set_page_config(page_title="Remit Reconciliation Engine",
                   page_icon="🧾", layout="wide")

GREEN_BG, RED_BG = "background-color: #e6f4ea", "background-color: #fce8e6"
CHECK = {True: "✅", False: "❌"}


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


def style_by_status(df: pd.DataFrame) -> "pd.io.formats.style.Styler":
    def row_style(row):
        css = GREEN_BG if row["status"] == "GREEN" else RED_BG
        return [css] * len(row)
    return df.style.apply(row_style, axis=1)


st.title("🧾 Remit Reconciliation Engine")
st.caption(
    "Reconciles synthetic utility-billing payments against remittances: "
    "**SUM(Payment)=Remit · SUM(UtilityCharge)=CustCharge · "
    "SUM(AdjustmentAmt)=Adjustments · (CustCharge+Adjustments)−Remit = reported R-C**. "
    "Duplicate-inflated columns are repaired by zero-out dedupe; irreconcilable "
    "accounts are flagged for manual review. All data is 100% synthetic and "
    "refreshed on a schedule by GitHub Actions."
)

if not DB_PATH.exists():
    st.error("warehouse/raw.duckdb not found — run the pipeline first "
             "(data_gen/generate.py → warehouse/load_raw.py → dbt build).")
    st.stop()

batches = query("""
    SELECT batch_id,
           min(remit_date)  AS cycle_date,
           count(*)         AS accounts
    FROM marts.fct_reconciliation
    GROUP BY 1 ORDER BY batch_id DESC
""")
freshness = query("SELECT max(generated_at) AS ts FROM raw.raw.payments")["ts"].iloc[0]

with st.sidebar:
    st.header("Filters")
    batch_id = st.selectbox(
        "Remit cycle (batch)", batches["batch_id"],
        format_func=lambda b: (
            f"{b} — {batches.set_index('batch_id').loc[b, 'cycle_date']} "
            f"({batches.set_index('batch_id').loc[b, 'accounts']} accts)"),
    )
    st.caption(f"Latest synthetic data generated at\n**{freshness}** (UTC)")
    st.divider()
    st.markdown(
        "**How to read this**\n\n"
        "🟢 GREEN — all four checks pass\n\n"
        "🔴 RED — at least one check failed\n\n"
        "Zero-out dedupe zeroes *duplicate* dollar amounts (never real ones) "
        "until detail ties to summary; anything still unmatched goes to "
        "manual review with a SOX-style adjustment note."
    )

export = query(f"""
    SELECT * FROM marts.recon_export
    WHERE batch_id = '{batch_id}'
    ORDER BY status DESC, account_id
""")

n = len(export)
n_green = int((export["status"] == "GREEN").sum())
n_review = int(export["needs_manual_review"].sum())
open_rc = float(
    export.loc[export["computed_rc_difference"].abs() > 0.01,
               "computed_rc_difference"].abs().sum())
zeroed_rows = int(export["total_zeroed_rows"].sum())

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Accounts in cycle", n)
c2.metric("Match rate", f"{n_green / n:.1%}" if n else "—")
c3.metric("🟢 GREEN", n_green)
c4.metric("🔴 RED", n - n_green)
c5.metric("Manual review", n_review)
c6.metric("Open R-C differences", f"${open_rc:,.2f}")

trend = query("""
    SELECT batch_id,
           min(remit_date)                          AS cycle_date,
           count(*)                                 AS accounts,
           count(*) FILTER (status = 'GREEN')       AS green,
           round(100.0 * count(*) FILTER (status = 'GREEN') / count(*), 1)
                                                    AS match_rate_pct
    FROM marts.fct_reconciliation
    GROUP BY 1 ORDER BY 1
""")
if len(trend) > 1:
    st.altair_chart(
        alt.Chart(trend).mark_line(point=True).encode(
            x=alt.X("batch_id:N", title="remit cycle"),
            y=alt.Y("match_rate_pct:Q", title="match rate %",
                    scale=alt.Scale(domain=[0, 100])),
            tooltip=["batch_id", "cycle_date", "accounts", "green",
                     "match_rate_pct"],
        ).properties(height=180),
        use_container_width=True)
else:
    st.caption("📈 Match-rate trend appears once the scheduled refresh adds "
               "a second remit cycle.")

DISPLAY_COLS = {
    "account_id": "Account",
    "customer_name": "Customer",
    "status": "status",
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
    view = df[list(DISPLAY_COLS)].rename(columns=DISPLAY_COLS)
    for col in ["Σ Pay = Remit", "Σ Chg = CustChg", "Σ Adj = Adjust", "R-C ties"]:
        view[col] = view[col].map(CHECK)
    st.dataframe(
        style_by_status(view).format(
            {"Remit $": "${:,.2f}", "R-C computed": "${:,.2f}",
             "R-C reported": "${:,.2f}"}),
        use_container_width=True, hide_index=True,
        column_config={"status": st.column_config.TextColumn(width="small")})


tab_all, tab_matched, tab_unmatched, tab_review, tab_sox, tab_drill = st.tabs(
    ["All accounts", "🟢 Matched", "🔴 Unmatched", "🔍 Manual review",
     "🗒️ SOX approval queue", "🔬 Account drill-down"])

with tab_all:
    show_export(export)
with tab_matched:
    show_export(export[export["status"] == "GREEN"])
with tab_unmatched:
    show_export(export[export["status"] == "RED"])
with tab_review:
    st.caption("Detail column could not be tied to its summary even after "
               "zeroing every eligible duplicate — a human has to look.")
    show_export(export[export["needs_manual_review"]])
with tab_sox:
    st.caption(f"{zeroed_rows} duplicate row(s) zeroed this cycle. Zero-out "
               "adjustments alter no real amounts and require manager sign-off.")
    sox = export[export["sox_adjustment_note"].notna()]
    show_export(sox)
with tab_drill:
    acct = st.selectbox("Account", export["account_id"], key="drill")
    hdr = export[export["account_id"] == acct].iloc[0]
    st.markdown(
        f"**{hdr['customer_name']}** · {acct} · cycle {batch_id} — "
        f"{'🟢 GREEN' if hdr['status'] == 'GREEN' else '🔴 RED'}  \n"
        f"_{hdr['notes']}_")
    for label, table, id_col in [
            ("Payments (target: remit)", "fct_payments", "payment_id"),
            ("Utility charges (target: CustCharge)", "fct_utility_charges", "charge_id"),
            ("Adjustments (target: Adjustments)", "fct_adjustments", "adjustment_id")]:
        detail = query(f"""
            SELECT * FROM marts.{table}
            WHERE account_id = '{acct}' AND batch_id = '{batch_id}'
            ORDER BY {id_col}
        """)
        st.markdown(f"**{label}**")
        if detail.empty:
            st.caption("no detail rows this cycle")
        else:
            def dup_style(row):
                if row["is_zeroed"]:
                    return ["background-color: #fff3cd"] * len(row)
                return [""] * len(row)
            st.dataframe(detail.style.apply(dup_style, axis=1),
                         use_container_width=True, hide_index=True)

st.divider()
st.caption(
    "Synthetic demo — no real customer, company, or billing data. "
    "Pipeline: Python generator → DuckDB → dbt (staging/intermediate/marts, "
    "43 tests) → this dashboard. Source: "
    "[github.com/jelendu/remit-reconciliation-engine]"
    "(https://github.com/jelendu/remit-reconciliation-engine)")
