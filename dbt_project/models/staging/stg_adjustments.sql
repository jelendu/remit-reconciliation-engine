select
    adjustments_id,
    account_id,
    batch_id,
    cast(adjustments_amount as decimal(12, 2)) as adjustments_amount
from {{ source('raw', 'adjustments') }}
