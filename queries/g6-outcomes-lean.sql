-- G6 (LEAN) — success rate + gas burnt, last 30 days.
-- Same query as g6-outcomes.sql with a 30-day window (the variant
-- scripts/fetch.py runs; it produced the shipped data/bq_g6_outcomes.csv).
-- `status` column verified via INFORMATION_SCHEMA on 2026-11-12.
SELECT
  block_date AS date,
  COUNT(*) AS outcomes,
  COUNTIF(status LIKE '%SUCCESS%') AS successful_outcomes,
  SAFE_DIVIDE(COUNTIF(status LIKE '%SUCCESS%'), COUNT(*)) AS success_rate,
  SUM(gas_burnt) AS gas_burnt_total
FROM `bigquery-public-data.crypto_near_mainnet_us.execution_outcomes`
WHERE block_date BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
  AND CURRENT_DATE()
GROUP BY 1
ORDER BY 1;
