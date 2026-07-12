-- Zero-out may ONLY zero duplicate occurrences, and may only ever set an
-- amount to exactly 0 or leave it untouched — real amounts are never altered.
-- Rows returned = violations.

{% set zeroed_models = ['int_payments_zeroed', 'int_charges_zeroed', 'int_adjustments_zeroed'] %}

{% for model in zeroed_models %}
select
    '{{ model }}' as source_model,
    record_id,
    account_id,
    batch_id,
    original_amount,
    adjusted_amount,
    is_duplicate,
    is_zeroed
from {{ ref(model) }}
where (is_zeroed and not is_duplicate)
   or (adjusted_amount not in (0, original_amount))
{% if not loop.last %}union all{% endif %}
{% endfor %}
