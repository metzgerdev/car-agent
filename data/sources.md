https://www.kaggle.com/datasets/austinreese/craigslist-carstrucks-data
# Multi-source data plan

This project is a portfolio demonstration of AI engineering. The data does
not need to be live or production-ready; the goal is to show how an agent can
combine distinct sources while keeping schemas, provenance, and source scope
explicit.

## Source roles

| Source | Role in the demo | Boundary model | Normalized output |
| --- | --- | --- | --- |
| [Craigslist used-car snapshot](https://www.kaggle.com/datasets/austinreese/craigslist-carstrucks-data) | Broad marketplace inventory: asking price, mileage, listing text, location, and seller-provided attributes | `CraigslistVehicleRow` | `CraigslistInventoryCandidate`, then `Vehicle` after required enrichment |
| [NHTSA vPIC](https://vpic.nhtsa.dot.gov/api/) | VIN decoding and vehicle identity/specification normalization | `NHTSAVPICResponse` / `NHTSAVPICResult` | Provenance-backed `VehicleFact(topic="identity")` |
| [NHTSA recalls](https://www.nhtsa.gov/nhtsa-datasets-and-apis) | Safety recall and campaign context | `NHTSARecallResponse` / `NHTSARecallRecord` | Provenance-backed `VehicleFact(topic="safety_recall")` |
| [EPA FuelEconomy.gov](https://www.fueleconomy.gov/feg/ws/) | Fuel type, MPG, estimated fuel cost, emissions, drivetrain, and related configuration data | `EPAFuelEconomyVehicle` | Provenance-backed efficiency, ownership, emissions, and specification facts |
| Local knowledge fixture | Curated ownership and driving notes for the sales conversation | Existing `VehicleFact` records | Model-specific retrieved facts |
| Synthetic service-history fixture | Listing-level maintenance events used to demonstrate a second inventory enrichment path | `ServiceRecord` | Dedicated `retrieve_service_history` tool output, explicitly marked `synthetic_demo` |
| [Car and Driver](https://www.caranddriver.com/) / [MotorTrend](https://www.motortrend.com/) | Editorial context for a matched model: a link plus a short paraphrased summary | `MagazineReview` | UI review modal; editorial context remains separate from canonical vehicle facts |

## Pipeline

1. Stream the large Craigslist CSV through `CraigslistVehicleRow` rather than
   loading the whole file into memory.
2. Normalize marketplace fields into a typed
   `CraigslistInventoryCandidate`, preserving the original listing URL and
   source row ID.
3. Use a VIN, when present, to associate NHTSA vPIC identity facts. Use
   year/make/model and matching options to associate EPA configuration facts.
4. Resolve required inventory fields explicitly. For example, horsepower is
   not reliably present in the marketplace source, so the candidate cannot
   become a canonical `Vehicle` until horsepower enrichment is supplied.
5. Store inventory observations and external facts separately. No source
   silently overwrites another source's fields.
6. Expose the resulting facts through the existing retrieval tool so the
   CrewAI agent can use source-grounded information in its response and trace.
7. Keep listing-level service history separate from general knowledge facts.
   The checked-in records and fallback records for source rows are synthetic,
   typed as `ServiceRecord`, and retrieved only through
   `retrieve_service_history`.

## Source precedence and join keys

- Craigslist owns listing-specific observations: asking price, mileage,
  listing description, location, and the marketplace URL.
- NHTSA owns VIN identity and safety-recall context.
- EPA owns fuel-economy and emissions estimates for a vehicle configuration.
- A Craigslist row ID becomes the stable demo `vehicle_id` namespace; VIN is
  retained as a source attribute and is not used as the only join key because
  many marketplace rows omit it.
- EPA matches are configuration-level matches, not claims about the physical
  condition of a particular used vehicle.

## Provenance contract

Every normalized inventory record and external fact carries:

- `source_url`: provider endpoint, listing URL, or a local recorded-fixture URI;
- `source_type`: for example `craigslist_snapshot`, `nhtsa_vpic`,
  `nhtsa_recalls`, or `fueleconomy_api`;
- `retrieved_at`: an ISO-8601 timestamp for the ingestion or fixture capture;
- `source_record_id` when the provider supplies one;
- `license` when the source license is known.

The Craigslist data is intentionally treated as a static demo snapshot.
Freshness and listing availability are outside the acceptance gate. The
engineering acceptance criteria are typed validation, source separation,
provenance, deterministic recorded fixtures, and inspectable retrieval.

Magazine reviews are curated external links matched by make/model. Their
summaries are brief paraphrases for navigation and context, not copied article
text or claims about the condition of a specific listing.

Service history is synthetic demo enrichment rather than an external provider
claim. Every generated record carries `source: synthetic_demo`, and the agent
discloses that limitation before suggesting a pre-purchase inspection.

## Implementation status

- Pydantic boundary models and streaming CSV row validation are implemented in
  `src/car_agent/source_models.py` and `src/car_agent/source_adapters.py`.
- `data/craigslist_sample.csv` is a four-row, source-shaped sample for the
  first end-to-end ingestion slice. `car-agent-ingest-craigslist` streams those
  rows, requires explicit horsepower enrichment, and writes canonical records
  with `craigslist_snapshot` provenance to SQLite.
- `CAR_AGENT_INVENTORY_PATH` lets the runtime repository read that generated
  SQLite inventory instead of the illustrative JSON fixture.
- Recorded NHTSA vPIC, NHTSA recall, EPA, and Craigslist fixtures provide
  offline tests for the adapter contract.
- Curated Car and Driver and MotorTrend links are validated with Pydantic and
  served by the review endpoint for the browser demo.
- Live provider calls remain opt-in; the default test suite never needs a
  network connection or API key.

The checked-in CSV is only a small offline demonstration sample with
source-shaped fields and placeholder listing URLs. The full Craigslist export
is intentionally not checked into the repository and can be processed with the
same command after download.
