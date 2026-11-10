# Sources, data, and licenses

## Project code and synthetic demo

Original project code, documentation, and invented `demo/origins.json` values are
provided under the [MIT license](LICENSE). Demo values do not describe real
individuals, campaigns, or FEC financial findings.

## FEC source data

The live importer downloads Federal Election Commission bulk files directly from
the [FEC bulk data page](https://www.fec.gov/data/browse-data/?tab=bulk-data).
Downloaded archives and local database records are not distributed in this
repository. The project's code license does not license third-party source data
or override FEC terms and applicable source-data rules.

Source layouts and interpretation:

- [Candidate master](https://www.fec.gov/campaign-finance-data/candidate-master-file-description/)
- [Committee master](https://www.fec.gov/campaign-finance-data/committee-master-file-description/)
- [Candidate-committee links](https://www.fec.gov/campaign-finance-data/candidate-committee-linkage-file-description/)
- [Individual contributions](https://www.fec.gov/campaign-finance-data/contributions-individuals-file-description/)

The individual file is not every donation. This project preserves amendments,
memos, and signed amounts, and does not represent exploratory raw sums as official
fundraising totals. See [the analysis policy](docs/data-model.md#contribution-origins-analysis-policy).

## Map boundaries

`src/fec_explorer/resources/us-states-10m.json` comes from us-atlas 3, which derives boundaries from
US Census Bureau cartographic files. Its upstream ISC license and copyright are
retained in [assets/us-atlas-LICENSE](assets/us-atlas-LICENSE).
The same license is bundled beside the map resource in distributions.
See [asset provenance](assets/README.md). The screenshot/preview uses these same
boundaries; its contribution values are synthetic.

## Dependencies

Python dependencies retain their own licenses. See the installed packages and
the requirements files for the libraries used; MIT licensing of this repository
does not replace those licenses.
