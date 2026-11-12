-- G1 — Daily active accounts (daily active signers).
-- Chart: daily active accounts (line).
-- One sentence: how many distinct accounts signed a transaction on NEAR
-- each day.
SELECT
  block_date AS date,
  COUNT(DISTINCT signer_account_id) AS daily_active_signers
FROM `bigquery-public-data.crypto_near_mainnet_us.transactions`
WHERE block_date BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 365 DAY)
  AND CURRENT_DATE()
GROUP BY 1
ORDER BY 1;
