-- The analyst-facing export view: one row per account x cycle with
-- green/red status, per-check verdicts, notes, and SOX adjustment notes.

select
    f.recon_id,
    f.account_id,
    a.customer_name,
    f.batch_id,
    f.remit_date,
    f.status,
    case when f.status = 'GREEN' then 'green' else 'red' end as status_color,
    f.payment_check_passed,
    f.charge_check_passed,
    f.adjustment_check_passed,
    f.rc_check_passed,
    f.needs_manual_review,
    f.remit_amount,
    f.payment_adjusted_sum,
    f.cust_charge_amount,
    f.charge_adjusted_sum,
    f.adjustments_amount,
    f.adjustment_adjusted_sum,
    f.computed_rc_difference,
    f.reported_rc_difference,
    f.total_zeroed_rows,
    f.total_zeroed_amount,
    coalesce(nullif(f.notes, ''), 'clean pass — no intervention required') as notes,
    f.sox_adjustment_note,
    f.approval_status
from {{ ref('fct_reconciliation') }} f
join {{ ref('dim_account') }} a
    on f.account_id = a.account_id
