{#
  zero_out_dedupe — the core dedupe rule of the engine.

  Where duplicate dollar amounts inflate a detail column, ZERO the duplicate
  occurrences (never alter a real amount, never delete a record) until the
  detail sum matches the summary target. If the column still does not match
  after every eligible duplicate is zeroed, the account is left unmatched and
  flows to manual review downstream.

  Duplicates = 2nd+ occurrence of the same dollar amount within one
  account + batch. Zeroing is applied greedily in deterministic order and
  only while it moves the detail sum TOWARD the target:
    - detail overshoots target  -> zero positive-amount duplicates
    - detail undershoots target -> zero negative-amount duplicates
      (a duplicated credit deflates the sum, so zeroing it raises the sum)

  Emits one row per detail record with original vs adjusted amount and flags.
#}
{% macro zero_out_dedupe(detail_ref, id_col, amount_col, target_ref, target_col) %}

with detail as (

    select
        {{ id_col }}                    as record_id,
        account_id,
        batch_id,
        {{ amount_col }}                as original_amount,
        row_number() over (
            partition by account_id, batch_id, {{ amount_col }}
            order by {{ id_col }}
        )                               as occurrence_num
    from {{ detail_ref }}

),

targets as (

    select
        account_id,
        batch_id,
        {{ target_col }} as target_amount
    from {{ target_ref }}

),

enriched as (

    select
        d.*,
        t.target_amount,
        sum(d.original_amount) over (
            partition by d.account_id, d.batch_id
        ) as raw_detail_sum
    from detail d
    left join targets t
        on  d.account_id = t.account_id
        and d.batch_id   = t.batch_id

),

with_running as (

    select
        *,
        raw_detail_sum - coalesce(target_amount, 0) as excess_amount,
        sum(case when occurrence_num > 1 and original_amount > 0
                 then original_amount else 0 end) over (
            partition by account_id, batch_id
            order by occurrence_num, record_id
            rows between unbounded preceding and current row
        ) as pos_dup_running,
        sum(case when occurrence_num > 1 and original_amount < 0
                 then original_amount else 0 end) over (
            partition by account_id, batch_id
            order by occurrence_num, record_id
            rows between unbounded preceding and current row
        ) as neg_dup_running

    from enriched

),

flagged as (

    select
        *,
        occurrence_num > 1 as is_duplicate,
        coalesce(
            occurrence_num > 1
            and (
                (excess_amount >  0.005 and original_amount > 0
                     and pos_dup_running <= excess_amount + 0.005)
                or
                (excess_amount < -0.005 and original_amount < 0
                     and neg_dup_running >= excess_amount - 0.005)
            ),
            false
        ) as is_zeroed
    from with_running

)

select
    record_id,
    account_id,
    batch_id,
    original_amount,
    is_duplicate,
    is_zeroed,
    case when is_zeroed then 0 else original_amount end as adjusted_amount,
    target_amount,
    raw_detail_sum,
    excess_amount
from flagged

{% endmacro %}
