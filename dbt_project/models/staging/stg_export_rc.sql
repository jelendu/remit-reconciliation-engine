select
    export_id,
    account_id,
    batch_id,
    cast(export_date as date)                        as export_date,
    cast(reported_rc_difference as decimal(12, 2))   as reported_rc_difference
from {{ source('raw', 'export_rc') }}
