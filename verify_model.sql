-- Model counts by cycle; resolved + unresolved must equal raw links.
SELECT b.cycle, b.built_at, b.candidate_count, b.committee_count,
       b.resolved_link_count, b.unresolved_link_count,
       b.resolved_link_count + b.unresolved_link_count AS represented_links
FROM fec_model.builds b ORDER BY cycle;

-- All six model foreign keys should be validated.
SELECT conrelid::regclass AS table_name, conname, convalidated,
       pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE connamespace='fec_model'::regnamespace AND contype='f'
ORDER BY table_name, conname;

SELECT * FROM fec_model.unresolved_links WHERE cycle=2024 ORDER BY source_line;
SELECT * FROM fec_model.unresolved_principal_committees WHERE cycle=2024;
SELECT * FROM fec_model.unresolved_committee_candidates WHERE cycle=2024;

-- Maryland principal committees with database-enforced relationships.
SELECT c.cand_name,c.cand_election_yr,c.cand_office,c.cand_office_district,m.cmte_id,m.cmte_nm
FROM fec_model.candidates c
JOIN fec_model.principal_committees p ON p.cycle=c.cycle AND p.cand_id=c.cand_id
JOIN fec_model.committees m ON m.cycle=p.cycle AND m.cmte_id=p.cmte_id
WHERE c.cycle=2024 AND c.cand_office_st='MD' AND c.cand_office IN ('H','S')
ORDER BY c.cand_name;
