-- G2 — Transaction counts.
-- Chart: daily transaction counts (line) + transactions per active account.
-- One sentence: how much raw activity the chain processes each day, and
-- whether each active account is doing more or less over time.
SELECT
  block_date AS date,
  COUNT(*) AS tx_count,
  COUNT(DISTINCT signer_account_id) AS daily_active_signers,
  SAFE_DIVIDE(COUNT(*), COUNT(DISTINCT signer_account_id)) AS tx_per_active_account
FROM `bigquery-public-data.crypto_near_mainnet_us.transactions`
WHERE block_date BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 365 DAY)
  AND CURRENT_DATE()
GROUP BY 1
ORDER BY 1;
