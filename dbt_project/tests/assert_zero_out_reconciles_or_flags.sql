-- The zero-out rule must hold within tolerance ($0.01):
--   (a) any check marked passed must actually tie out after dedupe, and
--   (b) any account whose detail still doesn't match after zeroing every
--       eligible duplicate MUST be flagged for manual review.
-- Rows returned = violations.

select
    account_id,
    batch_id,
    check_name,
    'marked passed but residual exceeds tolerance' as problem
from {{ ref('int_recon_rollup') }}
where check_passed
  and residual_after_dedupe > 0.01

union all

select
    account_id,
    batch_id,
    'any'                                          as check_name,
    'detail check failed but not flagged for manual review' as problem
from {{ ref('fct_reconciliation') }}
where not (payment_check_passed and charge_check_passed and adjustment_check_passed)
  and not needs_manual_review
