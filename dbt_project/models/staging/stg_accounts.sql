select
    account_id,
    customer_name,
    service_type,
    city,
    state,
    cast(enrolled_date as date) as enrolled_date
from {{ source('raw', 'accounts') }}
