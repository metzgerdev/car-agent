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

## Implementation status

- Pydantic boundary models and streaming CSV row validation are implemented in
  `src/car_agent/source_models.py` and `src/car_agent/source_adapters.py`.
- Recorded NHTSA vPIC, NHTSA recall, EPA, and Craigslist fixtures provide
  offline tests for the adapter contract.
- Live provider calls remain opt-in; the default test suite never needs a
  network connection or API key.
