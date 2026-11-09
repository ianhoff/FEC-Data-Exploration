# ADR 0001: Preserve raw data and separate modeling from exploration

Status: Accepted (documents the existing implementation)

## Context

FEC source records contain text identifiers, imperfect references, unusual years,
and reporting semantics which cannot be resolved safely by generic cleanup.
The project needs repeatable local ingestion and an interface for learning SQL.

## Decisions

1. Preserve source columns as text in `fec`, with empty strings mapped to NULL.
   Add cycle and physical source-line lineage. Parse strictly rather than silently
   replacing undecodable text or accepting changed layouts.
2. Replace a dataset/cycle in one transaction. Commit datasets independently so a
   failed large import does not discard successful smaller imports.
3. Keep foreign keys out of the raw layer. Profile missing references and preserve
   them for investigation. Reserve `fec_model` for validated types/relationships.
4. Make nationwide contributions an explicit separate import because of scale.
5. Use local Streamlit with parameterized read-only queries and a Maryland entry
   point. Retain national browsing to support investigation and learning.
6. Keep credentials out of code. Separate the importer connection from the
   analysis/modeling role and use local libpq authentication for routine access.

## Consequences

Raw tables are easy to audit, but every typed analysis must validate conversions.
Source-line keys change meaning across snapshots. Per-dataset commits permit
mixed refresh states; metadata must be checked before cross-table analysis.
The latest-success tracking table is not complete run history. Read-only app
transactions do not make the modeling account globally read-only.

Revisit these decisions when adding immutable snapshots, typed migrations,
scheduled ingestion, or a hosted application. Those capabilities are not implied
by the current implementation.
