-- G5 — Key chart, context leg: daily on-chain activity.
-- The key chart itself is two-source: Intents volume (Intents Explorer API
-- / DefiLlama, data/intents_volume_daily.csv) vs NEAR price (CoinGecko,
-- data/near_price_daily.csv). This SQL returns the on-chain activity series
-- (tx counts + active accounts) that the dashboard draws as the context
-- line; the join of the three series happens in scripts/build_dashboard.py.
-- One sentence: does Intents volume move first, or does it only follow
-- price and on-chain activity?
SELECT
  block_date AS date,
  COUNT(*) AS tx_count,
  COUNT(DISTINCT signer_account_id) AS daily_active_signers
FROM `bigquery-public-data.crypto_near_mainnet_us.transactions`
WHERE block_date BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 365 DAY)
  AND CURRENT_DATE()
GROUP BY 1
ORDER BY 1;
