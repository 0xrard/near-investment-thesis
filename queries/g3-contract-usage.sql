-- G3 — Contract usage: daily FUNCTION_CALL counts by receiving contract.
-- Chart: total daily contract calls (line) + top contracts table.
-- One sentence: which contracts people actually use, and whether usage
-- concentrates in a few contracts or spreads out.
-- Join pattern follows docs.near.org's example query
-- (receipt_actions -> receipt_origin_transaction -> transactions).
SELECT
  ra.block_date AS date,
  ra.receipt_receiver_account_id AS contract,
  COUNT(*) AS function_calls,
  COUNT(DISTINCT t.signer_account_id) AS unique_signers
FROM `bigquery-public-data.crypto_near_mainnet_us.receipt_actions` ra
JOIN `bigquery-public-data.crypto_near_mainnet_us.receipt_origin_transaction` ro
  ON ro.receipt_id = ra.receipt_id
JOIN `bigquery-public-data.crypto_near_mainnet_us.transactions` t
  ON ro.originated_from_transaction_hash = t.transaction_hash
WHERE ra.action_kind = 'FUNCTION_CALL'
  AND ra.block_date BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 365 DAY)
    AND CURRENT_DATE()
GROUP BY 1, 2
ORDER BY 1, 3 DESC;
