select
    remit_id,
    account_id,
    batch_id,
    cast(remit_date as date)               as remit_date,
    cast(remit_amount as decimal(12, 2))   as remit_amount
from {{ source('raw', 'remits') }}
