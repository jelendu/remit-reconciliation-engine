-- Grain: one row per account x remit cycle (batch).
-- Verdict of all four checks:
--   1. SUM(Payment)        = Remit        (after zero-out dedupe)
--   2. SUM(UtilityCharge)  = CustCharge   (after zero-out dedupe)
--   3. SUM(AdjustmentAmt)  = Adjustments  (after zero-out dedupe)
--   4. (CustCharge + Adjustments) - Remit = reported "R-C" difference

with checks as (

    select
        account_id,
        batch_id,
        bool_or(check_passed)        filter (where check_name = 'payment')    as payment_check_passed,
        max(raw_detail_sum)          filter (where check_name = 'payment')    as payment_raw_sum,
        max(adjusted_detail_sum)     filter (where check_name = 'payment')    as payment_adjusted_sum,
        max(zeroed_rows)             filter (where check_name = 'payment')    as payment_zeroed_rows,
        max(zeroed_amount)           filter (where check_name = 'payment')    as payment_zeroed_amount,
        max(residual_after_dedupe)   filter (where check_name = 'payment')    as payment_residual,

        bool_or(check_passed)        filter (where check_name = 'charge')     as charge_check_passed,
        max(raw_detail_sum)          filter (where check_name = 'charge')     as charge_raw_sum,
        max(adjusted_detail_sum)     filter (where check_name = 'charge')     as charge_adjusted_sum,
        max(zeroed_rows)             filter (where check_name = 'charge')     as charge_zeroed_rows,
        max(zeroed_amount)           filter (where check_name = 'charge')     as charge_zeroed_amount,
        max(residual_after_dedupe)   filter (where check_name = 'charge')     as charge_residual,

        bool_or(check_passed)        filter (where check_name = 'adjustment') as adjustment_check_passed,
        max(raw_detail_sum)          filter (where check_name = 'adjustment') as adjustment_raw_sum,
        max(adjusted_detail_sum)     filter (where check_name = 'adjustment') as adjustment_adjusted_sum,
        max(zeroed_rows)             filter (where check_name = 'adjustment') as adjustment_zeroed_rows,
        max(zeroed_amount)           filter (where check_name = 'adjustment') as adjustment_zeroed_amount,
        max(residual_after_dedupe)   filter (where check_name = 'adjustment') as adjustment_residual
    from {{ ref('int_recon_rollup') }}
    group by 1, 2

),

assembled as (

    select
        r.account_id || '|' || r.batch_id       as recon_id,
        r.account_id,
        r.batch_id,
        r.remit_date,
        r.remit_amount,
        cc.cust_charge_amount,
        adj.adjustments_amount,
        x.reported_rc_difference,
        (cc.cust_charge_amount + adj.adjustments_amount) - r.remit_amount
                                                as computed_rc_difference,
        c.*  exclude (account_id, batch_id)
    from {{ ref('stg_remits') }} r
    join {{ ref('stg_cust_charges') }} cc
        on  r.account_id = cc.account_id and r.batch_id = cc.batch_id
    join {{ ref('stg_adjustments') }} adj
        on  r.account_id = adj.account_id and r.batch_id = adj.batch_id
    join {{ ref('stg_export_rc') }} x
        on  r.account_id = x.account_id and r.batch_id = x.batch_id
    join checks c
        on  r.account_id = c.account_id and r.batch_id = c.batch_id

),

verdicts as (

    select
        *,
        abs(computed_rc_difference - reported_rc_difference) <= 0.01
                                                as rc_check_passed,
        coalesce(payment_zeroed_rows, 0)
            + coalesce(charge_zeroed_rows, 0)
            + coalesce(adjustment_zeroed_rows, 0) as total_zeroed_rows,
        coalesce(payment_zeroed_amount, 0)
            + coalesce(charge_zeroed_amount, 0)
            + coalesce(adjustment_zeroed_amount, 0) as total_zeroed_amount
    from assembled

)

select
    *,
    (payment_check_passed and charge_check_passed
        and adjustment_check_passed and rc_check_passed) as all_checks_passed,
    case when payment_check_passed and charge_check_passed
              and adjustment_check_passed and rc_check_passed
         then 'GREEN' else 'RED' end                     as status,
    -- zero-out exhausted and a detail column still does not tie out
    not (payment_check_passed and charge_check_passed and adjustment_check_passed)
                                                         as needs_manual_review,
    concat_ws('; ',
        case when payment_zeroed_rows > 0 then
            printf('zero-out: %d duplicate payment row(s) totaling $%.2f zeroed',
                   payment_zeroed_rows, cast(payment_zeroed_amount as double)) end,
        case when charge_zeroed_rows > 0 then
            printf('zero-out: %d duplicate charge row(s) totaling $%.2f zeroed',
                   charge_zeroed_rows, cast(charge_zeroed_amount as double)) end,
        case when adjustment_zeroed_rows > 0 then
            printf('zero-out: %d duplicate adjustment row(s) totaling $%.2f zeroed',
                   adjustment_zeroed_rows, cast(adjustment_zeroed_amount as double)) end,
        case when not payment_check_passed then
            printf('payment detail off by $%.2f after dedupe — manual review',
                   cast(payment_residual as double)) end,
        case when not charge_check_passed then
            printf('charge detail off by $%.2f after dedupe — manual review',
                   cast(charge_residual as double)) end,
        case when not adjustment_check_passed then
            printf('adjustment detail off by $%.2f after dedupe — manual review',
                   cast(adjustment_residual as double)) end,
        case when not rc_check_passed then
            printf('R-C mismatch: computed $%.2f vs reported $%.2f',
                   cast(computed_rc_difference as double),
                   cast(reported_rc_difference as double)) end,
        case when rc_check_passed and abs(computed_rc_difference) > 0.01 then
            printf('known R-C difference of $%.2f disclosed on export',
                   cast(computed_rc_difference as double)) end
    )                                                    as notes,
    case when total_zeroed_rows > 0 then
        printf(
            'SOX adjustment note: %d duplicate record(s) zeroed (payments %d, charges %d, adjustments %d) totaling $%.2f to reconcile detail to summary. Original amounts preserved — duplicates zeroed, no real amounts altered. Requires manager approval.',
            total_zeroed_rows,
            coalesce(payment_zeroed_rows, 0),
            coalesce(charge_zeroed_rows, 0),
            coalesce(adjustment_zeroed_rows, 0),
            cast(total_zeroed_amount as double))
    end                                                  as sox_adjustment_note,
    case when total_zeroed_rows > 0
         then 'PENDING MANAGER APPROVAL' end             as approval_status
from verdicts
