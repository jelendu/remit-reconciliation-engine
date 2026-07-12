"""Remit Reconciliation Engine — multi-page Streamlit app (entry point).

Pages:
  The problem            — what this is and why it exists (start here)
  Reconciliation workbench — watch the four checks run on any account
  Operations dashboard   — cycle KPIs, trend, exception queues
  Pipeline & tests       — dbt lineage DAG, 61 test results, live feed
  About this build       — what it demonstrates, origin story, stack
"""

import streamlit as st

import ui

st.set_page_config(page_title="Remit Reconciliation Engine",
                   page_icon="🧾", layout="wide")
ui.inject_css()

pages = {
    "Start here": [
        st.Page("views/story.py", title="The problem", icon="🧭", default=True),
    ],
    "The tool": [
        st.Page("views/workbench.py", title="Reconciliation workbench", icon="🔬"),
        st.Page("views/operations.py", title="Operations dashboard", icon="📊"),
    ],
    "Under the hood": [
        st.Page("views/pipeline.py", title="Pipeline & tests", icon="🛠️"),
        st.Page("views/about.py", title="About this build", icon="👋"),
    ],
}

nav = st.navigation(pages)

with st.sidebar:
    st.markdown(ui.live_badge(), unsafe_allow_html=True)
    st.caption(f"Latest synthetic batch: **{ui.freshness()}** (UTC)")
    st.markdown(f"[Source on GitHub]({ui.REPO_URL})")
    st.caption("100% synthetic data — no real customers, companies, or "
               "billing records.")

nav.run()
