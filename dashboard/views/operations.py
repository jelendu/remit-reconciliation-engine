"""Operations dashboard — cycle KPIs, trend, and exception queues."""

import altair as alt
import pandas as pd
import streamlit as st

import ui

st.title("📊 Operations dashboard")
st.caption("The analyst's morning view: how the latest remit cycle "
           "reconciled, what moved vs the previous cycle, and the queues "
           "that need a human.")

cycles = ui.cycles()
batches = list(cycles["batch_id"])[::-1]
batch_id = st.selectbox(
    "Remit cycle (batch)", batches,
    format_func=lambda b: (
        f"{b} — {pd.Timestamp(cycles.set_index('batch_id').loc[b, 'cycle_date']).date()} "
        f"({cycles.set_index('batch_id').loc[b, 'accounts']} accounts)"))

row = cycles.set_index("batch_id").loc[batch_id]
pos = cycles.index[cycles["batch_id"] == batch_id][0]
prev = cycles.iloc[pos - 1] if pos > 0 else None

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Accounts in cycle", int(row["accounts"]),
          delta=None if prev is None else int(row["accounts"] - prev["accounts"]),
          delta_color="off",
          help="Append cycles are smaller than the base build on purpose — "
               "only a subset of accounts remits each cycle.")
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

export = ui.export(batch_id)

left, right = st.columns((3, 2), gap="large")
with left:
    st.markdown("##### Match rate by remit cycle")
    base = alt.Chart(cycles).encode(
        x=alt.X("batch_id:N", title=None, axis=alt.Axis(labelAngle=0)))
    line = base.mark_line(color=ui.BLUE, strokeWidth=2).encode(
        y=alt.Y("match_rate_pct:Q", title="match rate %",
                scale=alt.Scale(domain=[0, 100])))
    pts = base.mark_point(filled=True, size=80, color=ui.BLUE).encode(
        y="match_rate_pct:Q",
        tooltip=[alt.Tooltip("batch_id", title="cycle"),
                 alt.Tooltip("accounts"), alt.Tooltip("green", title="GREEN"),
                 alt.Tooltip("red", title="RED"),
                 alt.Tooltip("match_rate_pct", title="match rate %")])
    last_label = base.transform_filter(
        alt.datum.batch_id == str(cycles["batch_id"].iloc[-1])
    ).mark_text(dy=-14, color=ui.BLUE_DARK, fontWeight="bold").encode(
        y="match_rate_pct:Q", text=alt.Text("match_rate_pct:Q", format=".1f"))
    st.altair_chart(ui.themed((line + pts + last_label).properties(height=230)),
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
        color=ui.BLUE, cornerRadiusEnd=4, height=20
    ).encode(
        x=alt.X("failed accounts:Q", title="accounts failing",
                axis=alt.Axis(format="d", tickMinStep=1)),
        y=alt.Y("check:N", title=None, sort=None),
        tooltip=["check", "failed accounts"])
    labels = bars.mark_text(align="left", dx=6, color=ui.INK2).encode(
        text="failed accounts:Q")
    st.altair_chart(ui.themed((bars + labels).properties(height=230)),
                    width="stretch")

tab_all, tab_matched, tab_unmatched, tab_review, tab_sox = st.tabs(
    ["All accounts", "🟢 Matched", "🔴 Unmatched", "🔍 Manual review",
     "🗒️ SOX approval queue"])

with tab_all:
    ui.show_export(export)
    st.download_button("⬇️ Download export (CSV)",
                       export.to_csv(index=False).encode(),
                       file_name=f"recon_export_{batch_id}.csv",
                       mime="text/csv")
with tab_matched:
    ui.show_export(export[export["status"] == "GREEN"])
with tab_unmatched:
    ui.show_export(export[export["status"] == "RED"])
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
            x=alt.X("computed_rc_difference:Q",
                    title="(CustCharge+Adjustments) − Remit, $"),
            y=alt.Y("account_id:N", title=None, sort=None),
            color=alt.Color("direction:N", title=None,
                            scale=alt.Scale(
                                domain=["remit short (owed)", "remit over"],
                                range=[ui.RED_DIVERGING, ui.BLUE])),
            tooltip=["account_id",
                     alt.Tooltip("computed_rc_difference",
                                 title="difference $", format="$,.2f")])
        st.altair_chart(
            ui.themed(bars.properties(height=max(120, 24 * len(diffs)))),
            width="stretch")
with tab_review:
    st.caption("Detail column could not be tied to its summary even after "
               "zeroing every eligible duplicate — a human has to look. "
               "Open any of these in the workbench to see why.")
    ui.show_export(export[export["needs_manual_review"]])
with tab_sox:
    st.caption(f"{int(row['zeroed_rows'])} duplicate row(s) zeroed this "
               "cycle. Zero-out adjustments alter no real amounts and "
               "require manager sign-off.")
    ui.show_export(export[export["sox_adjustment_note"].notna()])
