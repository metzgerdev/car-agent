# Phase 2 Data Source Policy

The active multi-source plan lives in [`data/sources.md`](../data/sources.md).
It defines the source roles, Pydantic boundary models, join strategy,
provenance contract, and demo scope. This document remains as the Phase 2
policy entry point for the repository documentation.

The project intentionally uses a static marketplace snapshot to demonstrate
multi-source ingestion and agent grounding. Freshness is not an acceptance
criterion; typed validation, provenance, source separation, and deterministic
recorded fixtures are.
