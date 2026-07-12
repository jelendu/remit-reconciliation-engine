"""Pipeline & tests — the engineering evidence, rendered from dbt's own artifacts."""

import pandas as pd
import streamlit as st

import ui

st.title("🛠️ Pipeline & tests")
st.caption(
    "Nothing on this page is hand-drawn: the lineage graph and test results "
    "below are parsed from dbt's own `manifest.json` and `run_results.json`, "
    "republished on every pipeline run.")

arts = ui.load_dbt()
if arts is None:
    st.error("dbt artifacts not found — run `python orchestration/refresh.py`.")
    st.stop()
manifest, run_results = arts

models = ui.model_timings(manifest, run_results)
tests = ui.test_results(manifest, run_results)

# ---- headline evidence -----------------------------------------------------
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("dbt models", len(models))
m2.metric("Data tests", len(tests))
m3.metric("Passing", int((tests["status"] == "PASS").sum()))
m4.metric("Failing", int((tests["status"] != "PASS").sum()))
m5.metric("Full build time",
          f"{models['time (s)'].sum() + tests['time (s)'].sum():.1f}s")

st.markdown(
    f"[![dbt CI]({ui.REPO_URL}/actions/workflows/dbt-ci.yml/badge.svg)]"
    f"({ui.REPO_URL}/actions/workflows/dbt-ci.yml) "
    f"[![Scheduled data refresh]({ui.REPO_URL}/actions/workflows/refresh-data.yml/badge.svg)]"
    f"({ui.REPO_URL}/actions/workflows/refresh-data.yml)")

st.divider()

# ---- lineage ---------------------------------------------------------------
st.subheader("Lineage — raw sources → staging → intermediate → marts")
st.markdown(
    "Star schema in the marts layer; the zero-out dedupe rule lives in the "
    "intermediate layer as one reusable macro instantiated three times "
    "(payments, charges, adjustments) plus a summary-driven rollup so an "
    "account with zero detail rows is still evaluated.")
legend = " &nbsp; ".join(
    f'<span class="rre-badge" style="background:{ui.LAYER_FILL[l]};'
    f'color:{ui.LAYER_FONT[l]};border-color:{ui.LAYER_FILL[l]}">{l}</span>'
    for l in ("source", "staging", "intermediate", "marts"))
st.markdown(legend, unsafe_allow_html=True)
st.graphviz_chart(ui.lineage_dot(manifest), width="stretch")

st.divider()

# ---- tests -----------------------------------------------------------------
st.subheader("Every test from the latest build")
colA, colB = st.columns((2, 3), gap="large")
with colA:
    st.markdown("**The two tests that guard the core business rule:**")
    with st.container(border=True):
        st.markdown(
            "**`assert_zero_out_reconciles_or_flags`**  \n"
            "Every check marked *passed* must tie out within $0.01 after "
            "dedupe, and every account still unmatched after zeroing every "
            "eligible duplicate must carry the manual-review flag. No silent "
            "failures.")
    with st.container(border=True):
        st.markdown(
            "**`assert_only_duplicates_zeroed`**  \n"
            "Zero-out may only touch *duplicate occurrences*, and an "
            "adjusted amount must be exactly `0` or the untouched original. "
            "Real amounts are never altered — the audit trail is enforced "
            "by a test, not a promise.")
    st.markdown(
        "Plus `unique` / `not_null` on every primary key staging→marts, "
        "`relationships` from each fact to `dim_account`, and "
        "`accepted_values` on status.")
with colB:
    def status_style(v: str) -> str:
        return (f"color: {ui.GOOD_TEXT}; font-weight: 700" if v == "PASS"
                else f"color: {ui.CRIT}; font-weight: 700")
    st.dataframe(
        tests.style.map(status_style, subset=["status"]),
        width="stretch", hide_index=True, height=420)

st.divider()

# ---- models & the live loop -------------------------------------------------
colC, colD = st.columns((3, 2), gap="large")
with colC:
    st.subheader("Models by layer")
    st.dataframe(models, width="stretch", hide_index=True, height=380)
with colD:
    st.subheader("The live loop")
    st.markdown(
        "Every 30 minutes a GitHub Action appends one synthetic remit cycle "
        "(the billing feed 'moving': new payments, cancellations, "
        "adjustments), reruns the full dbt build + tests, and commits the "
        "refreshed warehouse. Streamlit Cloud redeploys on the commit — "
        "so this app is never a static snapshot.")
    commits = ui.recent_commits()
    if commits is not None:
        st.markdown("**Recent pipeline commits** (live from the GitHub API):")
        st.dataframe(commits, width="stretch", hide_index=True, height=240)
    else:
        st.caption("GitHub API unreachable right now — see the "
                   f"[commit history]({ui.REPO_URL}/commits/main) directly.")
