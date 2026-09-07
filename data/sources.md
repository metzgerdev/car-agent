# Multi-source data plan

This project is a portfolio demonstration of AI engineering. The inventory is
deliberately a checked-in mock fixture with 100 deterministic records; the
goal is to show typed boundaries, provenance, source separation, and agent
grounding without requiring live marketplace ingestion.

## Source roles

| Source | Role in the demo | Boundary model | Normalized output |
| --- | --- | --- | --- |
| Checked-in mock inventory (`data/inventory.json`) | Canonical listing facts: price, mileage, description, configuration, provenance, and synthetic service history | `Vehicle` through `normalize_inventory_record` | Validated `Vehicle` records |
| Deterministic inventory generator (`scripts/generate_mock_inventory.py`) | Reproducible synthetic auction-style records inspired by common enthusiast-listing fields; preserves the six curated demo vehicles | Generator output validated by `normalize_inventory_record` | 94 generated `Vehicle` records with local provenance |
| [NHTSA vPIC](https://vpic.nhtsa.dot.gov/api/) | VIN decoding and vehicle identity/specification normalization | `NHTSAVPICResponse` / `NHTSAVPICResult` | Provenance-backed `VehicleFact(topic="identity")` |
| [NHTSA recalls](https://www.nhtsa.gov/nhtsa-datasets-and-apis) | Safety recall and campaign context | `NHTSARecallResponse` / `NHTSARecallRecord` | Provenance-backed `VehicleFact(topic="safety_recall")` |
| [EPA FuelEconomy.gov](https://www.fueleconomy.gov/feg/ws/) | Fuel type, MPG, estimated fuel cost, emissions, drivetrain, and related configuration data | `EPAFuelEconomyVehicle` | Provenance-backed efficiency, ownership, emissions, and specification facts |
| Local knowledge fixture | Curated ownership and driving notes for the sales conversation | Existing `VehicleFact` records | Model-specific retrieved facts |
| Synthetic service-history fixture | Listing-level maintenance events used to demonstrate a second inventory enrichment path | `ServiceRecord` | Dedicated `retrieve_service_history` tool output, explicitly marked `synthetic_demo` |
| [Car and Driver](https://www.caranddriver.com/) / [MotorTrend](https://www.motortrend.com/) | Editorial context for a matched model: a link plus a short paraphrased summary | `MagazineReview` | Chat/API review context kept separate from canonical vehicle facts |
| [Wikimedia Commons](https://commons.wikimedia.org/) | Real model-reference photos for the six curated gallery vehicles, with source-page and license metadata | Optional image fields on `Vehicle` | UI photo URL plus photographer, source page, and license credit |

## Pipeline

1. Run `scripts/generate_mock_inventory.py` when the fixture needs to be
   regenerated. It preserves the six curated demo vehicles and writes 94
   synthetic records, for exactly 100 total records.
2. Validate the checked-in JSON records with `normalize_inventory_record` and
   load them through `InventoryRepository`.
3. Use a VIN, when present in an enrichment fixture, to associate NHTSA vPIC
   identity facts. Use year/make/model and matching options to associate EPA
   configuration facts.
4. Store inventory observations and external facts separately. No source
   silently overwrites another source's fields.
5. Expose the resulting facts through retrieval tools so CrewAI can use
   source-grounded information in its response and trace.
6. Keep listing-level service history separate from general knowledge facts.
   The checked-in records are synthetic, typed as `ServiceRecord`, and
   retrieved only through `retrieve_service_history`.

## Source precedence and join keys

- The mock inventory owns listing-specific observations: asking price,
  mileage, description, configuration, and listing provenance.
- NHTSA owns VIN identity and safety-recall context.
- EPA owns fuel-economy and emissions estimates for a vehicle configuration.
- External facts enrich the mock listing but do not overwrite its canonical
  inventory fields.
- EPA matches are configuration-level matches, not claims about the physical
  condition of a particular used vehicle.

## Provenance contract

Every inventory record and external fact carries:

- `source_url`: provider endpoint or a local recorded-fixture URI;
- `source_type`: for example `illustrative_fixture`, `nhtsa_vpic`,
  `nhtsa_recalls`, or `fueleconomy_api`;
- `retrieved_at`: an ISO-8601 timestamp for the fixture capture or enrichment;
- `source_record_id` when the source supplies one;
- `license` when the source license is known.

Magazine reviews are curated external links matched by make/model. Their
summaries are brief paraphrases for navigation and context, not copied article
text or claims about the condition of a specific listing.

Service history is synthetic demo enrichment rather than an external provider
claim. Every generated record carries `source: synthetic_demo`, and the agent
discloses that limitation before suggesting a pre-purchase inspection.

## Implementation status

- `data/inventory.json` is the canonical 100-record mock inventory used by the
  app and tests. The first six curated records preserve the original demo
  conversations and carry exact-model reference photos; the remaining 94
  records are deterministic and synthetic.
- Generated records are intentionally auction-style rather than live listings:
  their descriptions include mileage, condition context, modification notes,
  documentation guidance, and synthetic service history. They do not copy
  listing text, VINs, or auction outcomes from Cars & Bids or Bring a Trailer.
- The six curated photo URLs point to Wikimedia Commons file derivatives. The
  app displays each source page, photographer, and license; generated listings
  without a mapped photo use a clearly labeled CSS fallback.
- Recorded NHTSA vPIC, NHTSA recall, and EPA fixtures provide offline tests for
  the enrichment adapter contract.
- Curated Car and Driver and MotorTrend links are validated with Pydantic and
  served by the review endpoint for the browser demo.
- Live provider calls remain opt-in; the default test suite never needs a
  network connection or API key.
