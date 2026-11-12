-- G6 — Success rate + gas burnt (supporting chart).
-- Chart: daily execution success rate (line) + gas burnt (line/bars).
-- One sentence: is the chain getting more reliable and cheaper to use,
-- or the opposite?
-- NOTE: verified 2026-11-12 via INFORMATION_SCHEMA: the status column
-- is `status` STRING (not `outcome_status`), `gas_burnt` FLOAT64.
-- The success test matches any status containing 'SUCCESS' because the
-- exact stored value (e.g. 'SUCCESS_VALUE') is schema-dependent.
-- execution_outcomes covers receipts as well as transactions, so daily
-- outcome counts run higher than daily transaction counts — expected.
SELECT
  block_date AS date,
  COUNT(*) AS outcomes,
  COUNTIF(status LIKE '%SUCCESS%') AS successful_outcomes,
  SAFE_DIVIDE(COUNTIF(status LIKE '%SUCCESS%'), COUNT(*)) AS success_rate,
  SUM(gas_burnt) AS gas_burnt_total
FROM `bigquery-public-data.crypto_near_mainnet_us.execution_outcomes`
WHERE block_date BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 365 DAY)
  AND CURRENT_DATE()
GROUP BY 1
ORDER BY 1;
