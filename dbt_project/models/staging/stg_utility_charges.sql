select
    charge_id,
    account_id,
    batch_id,
    cast(charge_date as date)              as charge_date,
    charge_type,
    cast(charge_amount as decimal(12, 2))  as charge_amount
from {{ source('raw', 'utility_charges') }}
