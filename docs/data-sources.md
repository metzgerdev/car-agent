# Phase 2 Data Source Policy

Phase 2 separates authoritative vehicle facts from marketplace observations. We retain a source reference and retrieval timestamp for every accepted inventory record, but we do not copy listing prose or images into the project.

## Selected sources

### NHTSA vPIC

The [NHTSA Vehicle Product Information Catalog API](https://vpic.nhtsa.dot.gov/api/) is the primary public source for vehicle identity and VIN/make/model normalization. It is useful for validating identifiers and specifications; it is not a used-car price source.

### FuelEconomy.gov

The [FuelEconomy.gov data downloads](https://www.fueleconomy.gov/feg/epadata/) provide public vehicle and fuel-economy records. We can use them for efficiency and related specification fields, retaining the dataset URL and retrieval date in provenance.

### Marketplace references

Bring a Trailer, Cars & Bids, and similar auction sites are useful for manually reviewing market context. Until each site’s current terms and any API/license explicitly permit automated reuse, the pipeline stores only a manually entered listing URL, auction metadata, and our own normalized fields. It does not scrape or bulk-copy listing content.

## Provenance contract

Each accepted inventory row must include:

- `source_url`: an `http`, `https`, or local fixture URI;
- `source_type`: for example `nhtsa_vpic`, `fueleconomy_csv`, `manual_listing_reference`, or `illustrative_fixture`;
- `retrieved_at`: an ISO-8601 timestamp;
- optional `source_record_id` and `license` fields.

The current `data/` files are illustrative fixtures and explicitly identify themselves as `internal-demo`; they are not claims about live inventory or market pricing.

The local normalization and SQLite ingestion contract is complete. Adapters for fetching NHTSA/EPA source data and a provenance-aware review step for manually entered auction references are the next Phase 2 sub-milestone.
