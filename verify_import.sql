-- Run in DBeaver against fec_project after the small import.
SELECT current_database() AS database_name, current_user AS database_user,
       inet_server_addr() AS server_address, inet_server_port() AS server_port;

-- Compare physical table counts with the importer tracking records.
WITH actual AS (
    SELECT 'candidates' AS dataset, cycle, count(*) AS actual_rows
    FROM fec.candidates GROUP BY cycle
    UNION ALL
    SELECT 'committees', cycle, count(*) FROM fec.committees GROUP BY cycle
    UNION ALL
    SELECT 'links', cycle, count(*) FROM fec.links GROUP BY cycle
)
SELECT a.*, i.row_count AS tracked_rows,
       a.actual_rows = i.row_count AS counts_match, i.imported_at
FROM actual a
LEFT JOIN fec.imports i USING (dataset, cycle)
ORDER BY cycle, dataset;

-- Profile business identifiers before adding unique constraints.
SELECT cycle, cand_id, count(*) AS records
FROM fec.candidates GROUP BY cycle, cand_id
HAVING count(*) > 1 OR cand_id IS NULL;

SELECT cycle, cmte_id, count(*) AS records
FROM fec.committees GROUP BY cycle, cmte_id
HAVING count(*) > 1 OR cmte_id IS NULL;

-- Missing references are findings to investigate, not rows to discard.
SELECT count(*) AS link_records,
       count(*) FILTER (WHERE NOT EXISTS (
           SELECT 1 FROM fec.candidates c
           WHERE c.cycle=l.cycle AND c.cand_id=l.cand_id
       )) AS without_candidate,
       count(*) FILTER (WHERE l.cmte_id IS NULL) AS missing_committee_id,
       count(*) FILTER (WHERE l.cmte_id IS NOT NULL AND NOT EXISTS (
           SELECT 1 FROM fec.committees m
           WHERE m.cycle=l.cycle AND m.cmte_id=l.cmte_id
       )) AS without_committee
FROM fec.links l WHERE cycle=2024;
