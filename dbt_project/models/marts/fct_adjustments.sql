select
    z.record_id            as adjustment_id,
    z.account_id,
    z.batch_id,
    s.adj_date,
    s.reason_code,
    z.original_amount,
    z.adjusted_amount,
    z.is_duplicate,
    z.is_zeroed
from {{ ref('int_adjustments_zeroed') }} z
join {{ ref('stg_adjustment_amts') }} s
    on z.record_id = s.adjustment_id
