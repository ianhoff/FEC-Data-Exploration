# ADR 0002: Enforce relationships in a separate snapshot model

Status: Accepted

## Context

Master IDs are unique and present in the checked 2022/2024 sources, but some
link references are absent. Raw foreign keys would prevent preserving those rows.
Developers also need real relationships visible in DBeaver.

## Decision

Copy master records into `fec_model` with cycle-aware business primary keys.
Copy fully resolved links with two enforced foreign keys; materialize all other
links separately with missing-reference flags. Represent validated principal-
committee and committee-candidate references in separate relationship tables,
each with two foreign keys. Keep original source references on masters and expose
their unresolved values through quality views. Do not invent placeholder entities.

Use versioned, checksum-checked SQL migrations and atomic selected-cycle model
refreshes. Reject duplicate/missing master keys instead of selecting arbitrary
winners. Record latest-build counts and source import metadata. Preserve the raw
layer and leave the large contributions model for separate design.

## Consequences

Model links alone are an accepted subset, not a complete representation of the
source; users must consult unresolved links and build counts. Rebuilding is explicit
after raw refreshes. Source attributes remain text, so validated relationships do
not imply validated dates, years, amounts, or financial attribution. Shared advisory
locking coordinates the provided scripts, not arbitrary database writers.
