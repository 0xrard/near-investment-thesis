-- 00-freshness.sql — RUN FIRST, on every run.
-- NEAR Lake (the AWS S3 source) was deprecated 2026-03-24 and no longer
-- indexes new blocks. If MAX(block_date) is months old, the on-chain leg
-- cannot speak about current usage: the dashboard says so, and the
-- Intents API becomes the fresh leg.
SELECT
  MAX(block_date) AS max_block_date,
  MAX(block_height) AS max_block_height,
  COUNT(*) AS blocks_in_range
FROM `bigquery-public-data.crypto_near_mainnet_us.blocks`
WHERE block_date BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 365 DAY)
  AND CURRENT_DATE();
