-- Versioned initial model. Run through build_model.py, not independently.
-- LIKE keeps source field types and NOT NULL markers, not raw indexes/keys.
CREATE TABLE fec_model.candidates (LIKE fec.candidates INCLUDING DEFAULTS);
ALTER TABLE fec_model.candidates ADD PRIMARY KEY (cycle, cand_id);
ALTER TABLE fec_model.candidates ADD UNIQUE (cycle, source_line);

CREATE TABLE fec_model.committees (LIKE fec.committees INCLUDING DEFAULTS);
ALTER TABLE fec_model.committees ADD PRIMARY KEY (cycle, cmte_id);
ALTER TABLE fec_model.committees ADD UNIQUE (cycle, source_line);

CREATE TABLE fec_model.links (LIKE fec.links INCLUDING DEFAULTS);
ALTER TABLE fec_model.links ADD PRIMARY KEY (cycle, source_line);
ALTER TABLE fec_model.links ALTER COLUMN cand_id SET NOT NULL;
ALTER TABLE fec_model.links ALTER COLUMN cmte_id SET NOT NULL;
ALTER TABLE fec_model.links ADD CONSTRAINT links_candidate_fk
    FOREIGN KEY (cycle, cand_id) REFERENCES fec_model.candidates (cycle, cand_id);
ALTER TABLE fec_model.links ADD CONSTRAINT links_committee_fk
    FOREIGN KEY (cycle, cmte_id) REFERENCES fec_model.committees (cycle, cmte_id);
CREATE INDEX links_candidate_idx ON fec_model.links (cycle, cand_id);
CREATE INDEX links_committee_idx ON fec_model.links (cycle, cmte_id);

CREATE TABLE fec_model.unresolved_links (LIKE fec.links INCLUDING DEFAULTS);
ALTER TABLE fec_model.unresolved_links ADD PRIMARY KEY (cycle, source_line);
ALTER TABLE fec_model.unresolved_links ADD candidate_absent boolean NOT NULL;
ALTER TABLE fec_model.unresolved_links ADD committee_absent boolean NOT NULL;
ALTER TABLE fec_model.unresolved_links ADD CHECK (candidate_absent OR committee_absent);

-- Source references stay intact on masters; accepted relationships live here.
CREATE TABLE fec_model.principal_committees (
    cycle integer NOT NULL,
    cand_id text NOT NULL,
    cmte_id text NOT NULL,
    PRIMARY KEY (cycle, cand_id),
    FOREIGN KEY (cycle, cand_id) REFERENCES fec_model.candidates (cycle, cand_id),
    FOREIGN KEY (cycle, cmte_id) REFERENCES fec_model.committees (cycle, cmte_id)
);
CREATE INDEX principal_committees_committee_idx ON fec_model.principal_committees (cycle, cmte_id);

CREATE TABLE fec_model.committee_candidates (
    cycle integer NOT NULL,
    cmte_id text NOT NULL,
    cand_id text NOT NULL,
    PRIMARY KEY (cycle, cmte_id),
    FOREIGN KEY (cycle, cmte_id) REFERENCES fec_model.committees (cycle, cmte_id),
    FOREIGN KEY (cycle, cand_id) REFERENCES fec_model.candidates (cycle, cand_id)
);
CREATE INDEX committee_candidates_candidate_idx ON fec_model.committee_candidates (cycle, cand_id);

CREATE TABLE fec_model.builds (
    cycle integer PRIMARY KEY,
    built_at timestamptz NOT NULL DEFAULT now(),
    source_imports jsonb NOT NULL,
    candidate_count bigint NOT NULL,
    committee_count bigint NOT NULL,
    resolved_link_count bigint NOT NULL,
    unresolved_link_count bigint NOT NULL
);

CREATE VIEW fec_model.unresolved_principal_committees AS
SELECT c.cycle, c.source_line, c.cand_id, c.cand_pcc AS cmte_id
FROM fec_model.candidates c
WHERE c.cand_pcc IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM fec_model.committees m
    WHERE m.cycle=c.cycle AND m.cmte_id=c.cand_pcc
);

CREATE VIEW fec_model.unresolved_committee_candidates AS
SELECT m.cycle, m.source_line, m.cmte_id, m.cand_id
FROM fec_model.committees m
WHERE m.cand_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM fec_model.candidates c
    WHERE c.cycle=m.cycle AND c.cand_id=m.cand_id
);
