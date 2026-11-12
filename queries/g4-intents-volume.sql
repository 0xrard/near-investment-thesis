-- G4 — Intents swap volume (BigQuery proxy).
-- The CANONICAL G4 series comes from the Intents Explorer API / DefiLlama
-- via scripts/fetch.py (data/intents_volume_daily.csv). This file is the
-- on-chain proxy: daily FUNCTION_CALL counts and unique callers to the
-- Intents contracts — the leg sub-hypothesis B uses to test whether
-- Intents activity shows up on-chain.
-- FILL IN the contract list below with verified Intents contract addresses
-- from the docs before running. Until then the query returns zero rows,
-- which is honest, not a bug. Never guess an address.
WITH intents_contracts AS (
  SELECT contract_id FROM UNNEST([
    -- TODO: verified Intents contract addresses, e.g. from docs / explorer.
    'REPLACE-WITH-VERIFIED-INTENTS-CONTRACT'
  ]) AS contract_id
)
SELECT
  ra.block_date AS date,
  COUNT(*) AS intents_function_calls,
  COUNT(DISTINCT t.signer_account_id) AS unique_callers
FROM `bigquery-public-data.crypto_near_mainnet_us.receipt_actions` ra
JOIN `bigquery-public-data.crypto_near_mainnet_us.receipt_origin_transaction` ro
  ON ro.receipt_id = ra.receipt_id
JOIN `bigquery-public-data.crypto_near_mainnet_us.transactions` t
  ON ro.originated_from_transaction_hash = t.transaction_hash
JOIN intents_contracts ic
  ON ic.contract_id = ra.receipt_receiver_account_id
WHERE ra.action_kind = 'FUNCTION_CALL'
  AND ra.block_date BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 365 DAY)
    AND CURRENT_DATE()
GROUP BY 1
ORDER BY 1;
