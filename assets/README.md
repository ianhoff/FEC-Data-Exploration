# US state boundaries

`src/fec_explorer/resources/us-states-10m.json` is the unmodified states TopoJSON from us-atlas 3:
https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json

Source project: https://github.com/topojson/us-atlas (ISC license).
The data is derived from US Census Bureau cartographic boundaries.
See the bundled `us-atlas-LICENSE` for the upstream license.
The app loads this packaged file through importlib.resources and normalizes geometry IDs to integer FIPS codes
in memory. No contributor records are sent to a third-party map provider.
