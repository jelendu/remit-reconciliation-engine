select
    payment_id,
    account_id,
    batch_id,
    cast(payment_date as date)                as payment_date,
    payment_method,
    cast(payment_amount as decimal(12, 2))    as payment_amount
from {{ source('raw', 'payments') }}
