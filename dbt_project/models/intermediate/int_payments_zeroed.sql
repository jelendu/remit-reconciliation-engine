-- Check 1 detail side: SUM(Payment) must equal Remit.
-- Duplicate payment amounts are zeroed (never altered) to hit the remit target.
{{ zero_out_dedupe(
    ref('stg_payments'), 'payment_id', 'payment_amount',
    ref('stg_remits'), 'remit_amount'
) }}
