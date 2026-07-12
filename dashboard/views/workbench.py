"""Reconciliation workbench — watch the four checks run on a real account."""

import pandas as pd
import streamlit as st

import ui

st.title("🔬 Reconciliation workbench")
st.caption(
    "Pick an account — or jump straight to an interesting one — and see "
    "exactly what the engine did: every detail row, every sum, every repair, "
    "and the verdict. This is the per-account math the pipeline runs for the "
    "whole book every cycle.")

# ---- scenario quick-picks --------------------------------------------------
PICKS = {
    "repaired":  ("🔁 Duplicate repaired",
                  "status = 'GREEN' AND total_zeroed_rows > 0"),
    "review":    ("🚨 Manual review",
                  "needs_manual_review"),
    "misreport": ("🕵️ Misreported export",
                  "NOT rc_check_passed AND NOT needs_manual_review"),
    "clean":     ("✨ Clean pass",
                  "status = 'GREEN' AND total_zeroed_rows = 0"),
}


def find_example(condition: str) -> tuple[str, str] | None:
    hit = ui.query(f"""
        SELECT account_id, batch_id FROM marts.fct_reconciliation
        WHERE {condition}
        ORDER BY batch_id DESC, account_id LIMIT 1
    """)
    return None if hit.empty else (hit["account_id"][0], hit["batch_id"][0])


qcols = st.columns(len(PICKS))
for (key, (label, cond)), col in zip(PICKS.items(), qcols):
    if col.button(label, key=f"pick_{key}", width="stretch"):
        st.session_state["wb_pick"] = key

if pick := st.session_state.pop("wb_pick", None):
    if example := find_example(PICKS[pick][1]):
        st.session_state["wb_acct"], st.session_state["wb_batch"] = example

# ---- selectors -------------------------------------------------------------
cyc = ui.cycles()
batches = list(cyc["batch_id"])[::-1]
sel1, sel2 = st.columns((1, 2))
batch_default = st.session_state.get("wb_batch", batches[0])
batch_id = sel1.selectbox("Remit cycle", batches,
                          index=batches.index(batch_default))
accounts = ui.query(f"""
    SELECT f.account_id, a.customer_name, f.status
    FROM marts.fct_reconciliation f JOIN marts.dim_account a USING (account_id)
    WHERE f.batch_id = '{batch_id}' ORDER BY f.account_id
""")
acct_ids = list(accounts["account_id"])
acct_default = st.session_state.get("wb_acct", acct_ids[0])
acct = sel2.selectbox(
    "Account", acct_ids,
    index=acct_ids.index(acct_default) if acct_default in acct_ids else 0,
    format_func=lambda a: (
        f"{a} · {accounts.set_index('account_id').loc[a, 'customer_name']} "
        f"({'🟢' if accounts.set_index('account_id').loc[a, 'status'] == 'GREEN' else '🔴'})"))

f = ui.query(f"""
    SELECT * FROM marts.fct_reconciliation
    WHERE account_id = '{acct}' AND batch_id = '{batch_id}'
""").iloc[0]
name = accounts.set_index("account_id").loc[acct, "customer_name"]

chip = ('<span class="rre-chip green">🟢 GREEN — exports clean</span>'
        if f["status"] == "GREEN"
        else '<span class="rre-chip red">🔴 RED — at least one check failed</span>')
st.markdown(f"### {name} · `{acct}` · cycle {batch_id} &nbsp; {chip}",
            unsafe_allow_html=True)
st.markdown(f"_{f['notes'] or 'clean pass — no intervention required'}_")

st.divider()

# ---- step 1: the summary side ---------------------------------------------
st.markdown("#### ① What the summaries claim")
s1, s2, s3, s4 = st.columns(4)
s1.metric("Remit", f"${f['remit_amount']:,.2f}")
s2.metric("CustCharge", f"${f['cust_charge_amount']:,.2f}")
s3.metric("Adjustments", f"${f['adjustments_amount']:,.2f}")
s4.metric("Export's reported R-C diff", f"${f['reported_rc_difference']:,.2f}")

# ---- step 2: the three detail checks ---------------------------------------
st.markdown("#### ② Does the detail agree? (three sum checks + zero-out)")

DETAIL = [
    ("Payments", "fct_payments", "payment_id",
     ["payment_id", "payment_date", "payment_method"],
     "payment", "Remit", f["remit_amount"]),
    ("Utility charges", "fct_utility_charges", "charge_id",
     ["charge_id", "charge_date", "charge_type"],
     "charge", "CustCharge", f["cust_charge_amount"]),
    ("Adjustments", "fct_adjustments", "adjustment_id",
     ["adjustment_id", "adj_date", "reason_code"],
     "adjustment", "Adjustments", f["adjustments_amount"]),
]

for label, table, id_col, meta_cols, prefix, target_name, target in DETAIL:
    raw = f[f"{prefix}_raw_sum"]
    adj = f[f"{prefix}_adjusted_sum"]
    zeroed_n = int(f[f"{prefix}_zeroed_rows"] or 0)
    passed = bool(f[f"{prefix}_check_passed"])
    residual = f[f"{prefix}_residual"]

    verdict = ('<span class="ok">✅ ties out</span>' if passed
               else f'<span class="bad">❌ off by ${residual:,.2f} → manual review</span>')
    repair = (f' → after zero-out **\\${adj:,.2f}**' if zeroed_n else "")
    st.markdown(f"**{label}** — SUM(detail) = \\${raw:,.2f}{repair} "
                f"vs {target_name} \\${target:,.2f}")
    st.markdown(f'<div class="rre-math">Σ detail {"→ repaired " if zeroed_n else ""}'
                f'${adj:,.2f} &nbsp;−&nbsp; target ${target:,.2f} &nbsp;=&nbsp; '
                f'${adj - target:,.2f} &nbsp; {verdict}</div>',
                unsafe_allow_html=True)

    detail = ui.query(f"""
        SELECT * FROM marts.{table}
        WHERE account_id = '{acct}' AND batch_id = '{batch_id}'
        ORDER BY {id_col}
    """)
    if detail.empty:
        st.caption("No detail rows this cycle (a $0 summary with no rows "
                   "still passes — the rollup is summary-driven).")
        continue
    if zeroed_n:
        st.caption(f"🗒️ {zeroed_n} duplicate row(s) zeroed — amber below. "
                   "Original amounts preserved; nothing deleted or edited.")

    view = detail[meta_cols + ["original_amount", "adjusted_amount",
                               "is_duplicate", "is_zeroed"]].rename(columns={
        "original_amount": "original $", "adjusted_amount": "after zero-out $",
        "is_duplicate": "duplicate?", "is_zeroed": "zeroed?"})

    def zero_style(row):
        css = (f"background-color: {ui.WARN_TINT}; color: {ui.INK}"
               if row["zeroed?"] else f"color: {ui.INK}")
        return [css] * len(row)

    st.dataframe(
        view.style.apply(zero_style, axis=1).format(
            {"original $": "${:,.2f}", "after zero-out $": "${:,.2f}"}),
        width="stretch", hide_index=True)

# ---- step 3: the R-C identity ----------------------------------------------
st.markdown("#### ③ The R-C identity — does the export tell the truth?")
computed = f["computed_rc_difference"]
reported = f["reported_rc_difference"]
rc_ok = bool(f["rc_check_passed"])
rc_verdict = ('<span class="ok">✅ export agrees</span>' if rc_ok else
              '<span class="bad">❌ export misreports — R-C check fails</span>')
st.markdown(
    f'<div class="rre-math">(CustCharge ${f["cust_charge_amount"]:,.2f} + '
    f'Adjustments ${f["adjustments_amount"]:,.2f}) − Remit '
    f'${f["remit_amount"]:,.2f} = <b>${computed:,.2f}</b> computed &nbsp;vs&nbsp; '
    f'<b>${reported:,.2f}</b> reported &nbsp; {rc_verdict}</div>',
    unsafe_allow_html=True)
if rc_ok and abs(computed) > 0.01:
    st.info(f"A **known difference of ${computed:,.2f}** is disclosed on the "
            "export — the check passes because the export tells the truth "
            "about it; the amount stays visible as an open item.", icon="ℹ️")

# ---- step 4: verdict & routing ---------------------------------------------
st.markdown("#### ④ Verdict & routing")
with st.container(border=True):
    st.markdown(chip, unsafe_allow_html=True)
    checks = [("Σ Payment = Remit", f["payment_check_passed"]),
              ("Σ UtilityCharge = CustCharge", f["charge_check_passed"]),
              ("Σ AdjustmentAmt = Adjustments", f["adjustment_check_passed"]),
              ("R-C ties to export", rc_ok)]
    st.markdown("  \n".join(
        f"{ui.CHECK[bool(ok)]} {label}" for label, ok in checks))
    if bool(f["needs_manual_review"]):
        st.markdown('<span class="rre-chip amber">🔍 routed to manual review'
                    '</span>', unsafe_allow_html=True)
    if isinstance(f["sox_adjustment_note"], str):
        st.warning(f["sox_adjustment_note"], icon="🗒️")
        approved = st.session_state.get(f"appr_{acct}_{batch_id}", False)
        if approved:
            st.success("Adjustment approved (demo — resets on reload). In "
                       "production this writes an approval record with "
                       "approver + timestamp.", icon="✅")
        elif st.button("Approve zero-out adjustment (manager demo)",
                       key=f"btn_{acct}_{batch_id}"):
            st.session_state[f"appr_{acct}_{batch_id}"] = True
            st.rerun()
