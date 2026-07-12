"""About this build — what it demonstrates, where it came from, what's next."""

import streamlit as st

import ui

st.title("👋 About this build")

st.markdown(
    "In a previous analytics role I owned a recurring remittance "
    "reconciliation: billing extracts pulled from **SQL Server**, a book "
    "that changed every cycle as customers paid, cancelled, or were "
    "adjusted, and a reconciliation that lived in a very large Excel "
    "workbook — hours of manual tie-outs, duplicate hunting, and "
    "hand-written adjustment notes.\n\n"
    "This project rebuilds that workflow the way an engineering team would "
    "ship it: **generalized** (no employer data, code, or proprietary "
    "rules — every record here is synthetic and self-generated) and "
    "**productionized** — versioned SQL models, tests that enforce the "
    "business rule, CI, a scheduled feed, and this app as the analyst-facing "
    "product.")

st.divider()

st.subheader("What each part demonstrates")
rows = [
    ("Data modeling", "Star schema (dim + 3 facts + reconciliation fact), "
     "staging → intermediate → marts layering, summary-driven rollups"),
    ("Software engineering", "The zero-out dedupe rule as one reusable, "
     "parameterized dbt macro; modular pages; typed Python; idempotent "
     "loader; deterministic seeded generator"),
    ("Testing & data quality", "43 dbt tests incl. two singular tests that "
     "encode the business rule itself — visible on the Pipeline page, run "
     "on every push and every scheduled refresh"),
    ("Orchestration / CI-CD", "GitHub Actions: dbt CI on push + a 30-minute "
     "scheduled job that appends a cycle, rebuilds, tests, commits, and "
     "triggers a redeploy"),
    ("Domain judgment", "Repairs only what is provably a duplicate; refuses "
     "to force an unmatched account; discloses known differences; every "
     "repair carries a SOX-style approval note"),
    ("Product & design", "Self-explaining multi-page app, guided demo "
     "paths, validated accessible palette, empty states, cycle-over-cycle "
     "deltas"),
]
for skill, evidence in rows:
    c1, c2 = st.columns((1, 3))
    c1.markdown(f"**{skill}**")
    c2.markdown(evidence)

st.divider()

st.subheader("Stack")
st.markdown(
    "Python · DuckDB · dbt (dbt-duckdb) · Streamlit · Altair · GitHub "
    "Actions · Streamlit Community Cloud — deliberately zero-cost and fully "
    "reproducible: `pip install -r requirements.txt`, run the generator, "
    "loader, `dbt build`, `streamlit run`.")
st.markdown(
    "**Swap-in path for a cloud warehouse:** the dbt models are "
    "warehouse-agnostic SQL — point the profile at Snowflake/BigQuery and "
    "`dbt build --target snowflake`. The DuckDB file exists so the whole "
    "thing runs free and offline.")

st.divider()

st.subheader("Honest limits & next steps")
st.markdown(
    "- The committed `.duckdb` grows git history — fine for a demo, wrong "
    "for prod; the next step is object storage + an incremental strategy.\n"
    "- Approvals on the workbench are a UI demo; production would persist "
    "approver + timestamp.\n"
    "- Alerting (match-rate threshold → Slack) is designed but not built.\n\n"
    f"Source, README, and full history: [{ui.REPO_URL.split('//')[1]}]({ui.REPO_URL})")
