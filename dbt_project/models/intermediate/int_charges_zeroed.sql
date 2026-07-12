-- Check 2 detail side: SUM(UtilityCharge) must equal CustCharge.
{{ zero_out_dedupe(
    ref('stg_utility_charges'), 'charge_id', 'charge_amount',
    ref('stg_cust_charges'), 'cust_charge_amount'
) }}
