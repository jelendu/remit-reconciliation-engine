select
    account_id,
    customer_name,
    service_type,
    city,
    state,
    enrolled_date
from {{ ref('stg_accounts') }}
