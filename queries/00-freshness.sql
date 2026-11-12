-- 00-freshness.sql — RUN FIRST, on every run.
-- An older draft warned NEAR Lake (the AWS S3 source) was deprecated
-- 2026-03-24 and might stop indexing new blocks. That warning is outdated
-- for this dataset: MAX(block_date) was 2026-11-11 when checked live on
-- 12 Nov 2026 (height 224,135,609) — it is still updating. This query is
-- still the tripwire: if MAX(block_date) is months old, the on-chain leg
-- cannot speak about current usage, and the Intents API becomes the
-- fresh leg.
SELECT
  MAX(block_date) AS max_block_date,
  MAX(block_height) AS max_block_height,
  COUNT(*) AS blocks_in_range
FROM `bigquery-public-data.crypto_near_mainnet_us.blocks`
WHERE block_date BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 365 DAY)
  AND CURRENT_DATE();
