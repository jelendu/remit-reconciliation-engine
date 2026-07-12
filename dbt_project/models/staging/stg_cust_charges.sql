select
    cust_charge_id,
    account_id,
    batch_id,
    cast(cust_charge_amount as decimal(12, 2)) as cust_charge_amount
from {{ source('raw', 'cust_charges') }}
