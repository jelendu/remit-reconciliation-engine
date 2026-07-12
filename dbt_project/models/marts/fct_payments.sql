select
    z.record_id            as payment_id,
    z.account_id,
    z.batch_id,
    s.payment_date,
    s.payment_method,
    z.original_amount,
    z.adjusted_amount,
    z.is_duplicate,
    z.is_zeroed
from {{ ref('int_payments_zeroed') }} z
join {{ ref('stg_payments') }} s
    on z.record_id = s.payment_id
