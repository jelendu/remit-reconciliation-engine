-- One row per account x batch x check, driven from the SUMMARY side so an
-- account with zero detail rows (e.g. no adjustments and a $0 Adjustments
-- summary) still gets evaluated instead of silently disappearing.

{% set checks = [
    {'name': 'payment',
     'summary': 'stg_remits',      'target_col': 'remit_amount',
     'detail':  'int_payments_zeroed'},
    {'name': 'charge',
     'summary': 'stg_cust_charges', 'target_col': 'cust_charge_amount',
     'detail':  'int_charges_zeroed'},
    {'name': 'adjustment',
     'summary': 'stg_adjustments',  'target_col': 'adjustments_amount',
     'detail':  'int_adjustments_zeroed'},
] %}

{% for check in checks %}
select
    s.account_id,
    s.batch_id,
    '{{ check.name }}'                          as check_name,
    cast(s.{{ check.target_col }} as decimal(12, 2)) as target_amount,
    coalesce(d.raw_sum, 0)                      as raw_detail_sum,
    coalesce(d.adjusted_sum, 0)                 as adjusted_detail_sum,
    coalesce(d.detail_rows, 0)                  as detail_rows,
    coalesce(d.duplicate_rows, 0)               as duplicate_rows,
    coalesce(d.zeroed_rows, 0)                  as zeroed_rows,
    coalesce(d.zeroed_amount, 0)                as zeroed_amount,
    coalesce(d.zeroed_rows, 0) > 0              as zero_out_applied,
    abs(coalesce(d.adjusted_sum, 0) - s.{{ check.target_col }}) <= 0.01
                                                as check_passed,
    abs(coalesce(d.adjusted_sum, 0) - s.{{ check.target_col }})
                                                as residual_after_dedupe
from {{ ref(check.summary) }} s
left join (
    select
        account_id,
        batch_id,
        sum(original_amount)                            as raw_sum,
        sum(adjusted_amount)                            as adjusted_sum,
        count(*)                                        as detail_rows,
        count(*) filter (where is_duplicate)            as duplicate_rows,
        count(*) filter (where is_zeroed)               as zeroed_rows,
        sum(original_amount) filter (where is_zeroed)   as zeroed_amount
    from {{ ref(check.detail) }}
    group by 1, 2
) d
    on  s.account_id = d.account_id
    and s.batch_id   = d.batch_id
{% if not loop.last %}union all{% endif %}
{% endfor %}
