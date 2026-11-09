-- Run after the first import. Source fields are deliberately text.
SELECT * FROM fec.imports ORDER BY cycle, dataset;

SELECT cand_id, cand_name, cand_office, cand_office_district, cand_pcc
FROM fec.candidates
WHERE cycle = 2024 AND cand_office_st = 'MD'
ORDER BY cand_name;

-- Principal committee joins. Include cycle to avoid cross-cycle duplication.
SELECT c.cand_name, m.cmte_id, m.cmte_nm
FROM fec.candidates c
JOIN fec.committees m ON m.cycle=c.cycle AND m.cmte_id=c.cand_pcc
WHERE c.cycle=2024 AND c.cand_office_st='MD';

-- Run these only AFTER the contributions import:
SELECT cmte_id, name, city, state, employer, occupation,
       transaction_dt, transaction_amt, memo_cd, transaction_tp
FROM fec.contributions WHERE cycle=2024 LIMIT 20;

-- Parseable dollar values: exploratory totals, not official fundraising totals.
-- Retains raw amounts; no assumptions about amendments, memos or attribution.
SELECT state, COUNT(*) AS source_records,
       SUM(CASE WHEN btrim(transaction_amt) ~ '^[+-]?[0-9]+([.][0-9]+)?$'
                THEN btrim(transaction_amt)::numeric END) AS recorded_amount_sum
FROM fec.contributions
WHERE cycle=2024
GROUP BY state ORDER BY recorded_amount_sum DESC NULLS LAST;

-- How many amounts require inspection before creating a typed model?
SELECT COUNT(*) FILTER (WHERE transaction_amt IS NULL) AS missing_amounts,
       COUNT(*) FILTER (WHERE transaction_amt IS NOT NULL AND
          btrim(transaction_amt) !~ '^[+-]?[0-9]+([.][0-9]+)?$') AS nonnumeric_amounts
FROM fec.contributions WHERE cycle=2024;
