-- G3 (LEAN) — daily FUNCTION_CALL counts by receiving contract, last 7 days.
-- This is the variant scripts/fetch.py runs. The full 365-day version with
-- the receipt_origin_transaction -> transactions join (g3-contract-usage.sql,
-- gives unique_signers) scans ~2.4 TB and exceeds the 1 TB/month free quota.
-- Lean = receipt_actions only, no joins, no unique_signers, 7-day window.
-- Output columns: date, contract, function_calls (what build_dashboard.py reads).
SELECT
  block_date AS date,
  receipt_receiver_account_id AS contract,
  COUNT(*) AS function_calls
FROM `bigquery-public-data.crypto_near_mainnet_us.receipt_actions`
WHERE action_kind = 'FUNCTION_CALL'
  AND block_date BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
    AND CURRENT_DATE()
GROUP BY 1, 2
ORDER BY 1, 3 DESC;
