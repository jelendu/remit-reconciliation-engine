-- Check 3 detail side: SUM(AdjustmentAmt) must equal Adjustments.
-- Adjustments can be negative; the macro zeroes duplicated credits when the
-- detail sum undershoots the target.
{{ zero_out_dedupe(
    ref('stg_adjustment_amts'), 'adjustment_id', 'adjustment_amt',
    ref('stg_adjustments'), 'adjustments_amount'
) }}
