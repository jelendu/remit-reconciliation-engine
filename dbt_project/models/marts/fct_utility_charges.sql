select
    z.record_id            as charge_id,
    z.account_id,
    z.batch_id,
    s.charge_date,
    s.charge_type,
    z.original_amount,
    z.adjusted_amount,
    z.is_duplicate,
    z.is_zeroed
from {{ ref('int_charges_zeroed') }} z
join {{ ref('stg_utility_charges') }} s
    on z.record_id = s.charge_id
