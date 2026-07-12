select
    adjustment_id,
    account_id,
    batch_id,
    cast(adj_date as date)                  as adj_date,
    reason_code,
    cast(adjustment_amt as decimal(12, 2))  as adjustment_amt
from {{ source('raw', 'adjustment_amts') }}
