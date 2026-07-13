"""Landing page — the 10-second story, then guided paths in."""

import streamlit as st

import ui

cyc = ui.cycles()
latest = cyc.iloc[-1]

st.markdown(
    f"""
<div class="rre-hero">
  {ui.live_badge()}
  <h1>Payments come in. The books say something else.<br>
      This engine finds every mismatch — automatically.</h1>
  <p class="lead">
    A production-style rebuild of a real reconciliation workflow: a utility-billing
    remittance feed that <b>changes every cycle</b> — payments post, services get
    cancelled, adjustments land — reconciled not in a giant spreadsheet, but by a
    tested SQL pipeline that repairs what it can, proves what it did, and routes
    what it can't fix to a human.
  </p>
</div>
""",
    unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
with c1:
    st.page_link("views/workbench.py",
                 label="Watch it reconcile an account →", icon="🔬")
with c2:
    st.page_link("views/pipeline.py",
                 label="See the pipeline & 43 tests →", icon="🛠️")
with c3:
    st.page_link("views/operations.py",
                 label="Open the operations dashboard →", icon="📊")

st.divider()

# ---- the problem -----------------------------------------------------------
st.subheader("The problem this automates")
p1, p2, p3 = st.columns(3, gap="large")
with p1, st.container(border=True):
    st.markdown("**📡 The feed never sits still**")
    st.markdown(
        "Every remit cycle the billing system moves: new payments, service "
        "cancellations, meter corrections, goodwill credits. Yesterday's "
        "reconciliation is stale by design.")
with p2, st.container(border=True):
    st.markdown("**⚖️ Detail must tie to summary**")
    st.markdown(
        "Per account, three sums have to hold — `Σ Payment = Remit`, "
        "`Σ UtilityCharge = CustCharge`, `Σ AdjustmentAmt = Adjustments` — "
        "plus the R-C identity: `(CustCharge + Adjustments) − Remit` must "
        "equal the difference the export reports.")
with p3, st.container(border=True):
    st.markdown("**🧨 Spreadsheets don't scale**")
    st.markdown(
        "Done by hand this is hours of VLOOKUP against a changing extract, "
        "with no audit trail for the fixes. Duplicated rows quietly inflate "
        "a column and the whole account goes red.")

# ---- what the engine does --------------------------------------------------
st.subheader("What the engine does, per account, every cycle")
left, right = st.columns((3, 2), gap="large")
with left:
    for n, head, body in [
        (1, "Ingest the cycle's entities",
         "Payments, remits, charges, adjustments and the export land in a "
         "DuckDB warehouse (in the original workflow: SQL Server extracts)."),
        (2, "Run the four checks",
         "dbt models compare every detail column to its summary target and "
         "compute the R-C identity — all as tested, versioned SQL."),
        (3, "Repair duplicate inflation — zero-out dedupe",
         "When duplicate dollar amounts inflate a column, the engine zeroes "
         "the duplicate occurrences (never a real amount, never a delete) "
         "until detail ties to summary."),
        (4, "Route the outcome",
         "GREEN exports clean. RED shows exactly which check failed. "
         "Anything unfixable is flagged for manual review, and every repair "
         "carries a SOX-style adjustment note awaiting manager approval."),
    ]:
        st.markdown(
            f'<div class="rre-step"><div class="n">{n}</div>'
            f'<div class="t"><b>{head}</b><span>{body}</span></div></div>',
            unsafe_allow_html=True)
with right:
    st.graphviz_chart(f"""
digraph flow {{
  rankdir=TB; bgcolor="transparent";
  node [shape=box, style="rounded,filled", fontname="Segoe UI", fontsize=11,
        penwidth=0, margin="0.18,0.1"];
  edge [color="{ui.AXIS}", arrowsize=0.7];
  gen  [label="synthetic billing feed\\n(payments · cancellations · adjustments)", fillcolor="{ui.SURFACE2}"];
  duck [label="DuckDB warehouse", fillcolor="{ui.LAYER_FILL['staging']}"];
  dbt  [label="dbt — 18 models · 43 tests\\nzero-out dedupe · 4 checks", fillcolor="{ui.LAYER_FILL['intermediate']}"];
  app  [label="this app", fillcolor="{ui.LAYER_FILL['marts']}", fontcolor="white"];
  gha  [label="GitHub Actions\\nnew cycle every 30 min + CI", fillcolor="{ui.WARN_TINT}"];
  gen -> duck -> dbt -> app;
  gha -> gen [style=dashed];
  gha -> dbt [style=dashed];
}}
""", width="stretch")

st.divider()

# ---- live right now --------------------------------------------------------
st.subheader("Live right now")
st.markdown(
    f"Cycle **{latest['batch_id']}** just processed "
    f"**{int(latest['accounts'])} accounts**: "
    f"**{int(latest['green'])} reconciled clean** "
    f"({latest['match_rate_pct']:.1f}% match rate), "
    f"**{int(latest['red'])} flagged red**, "
    f"**{int(latest['manual_review'])} routed to manual review**, "
    f"**${latest['open_rc']:,.2f}** in open R-C differences, and "
    f"**{int(latest['zeroed_rows'])} duplicate rows zeroed** with SOX notes "
    "pending approval. In ~30 minutes a GitHub Action will append the next "
    "cycle and these numbers will change.")

g1, g2, g3 = st.columns(3)
with g1, st.container(border=True):
    st.markdown("**🔁 See a duplicate get repaired**")
    st.markdown("An account whose payment column was inflated by a duplicate "
                "row — watch the engine zero it and tie out.")
    if st.button("Show me →", key="go_fixed"):
        st.session_state["wb_pick"] = "repaired"
        st.switch_page("views/workbench.py")
with g2, st.container(border=True):
    st.markdown("**🚨 See an account fail into manual review**")
    st.markdown("A real shortfall no dedupe can explain — the engine refuses "
                "to force it and hands it to a human.")
    if st.button("Show me →", key="go_review"):
        st.session_state["wb_pick"] = "review"
        st.switch_page("views/workbench.py")
with g3, st.container(border=True):
    st.markdown("**🕵️ See a misreported export get caught**")
    st.markdown("Sums all tie, but the export claims a difference that "
                "doesn't exist. The R-C check catches the lie.")
    if st.button("Show me →", key="go_misreport"):
        st.session_state["wb_pick"] = "misreport"
        st.switch_page("views/workbench.py")
