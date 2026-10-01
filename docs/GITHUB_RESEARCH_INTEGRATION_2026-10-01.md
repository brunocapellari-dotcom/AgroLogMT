# AgroLog MT — GitHub Research Integration 2026-10-01

Status: APPROVED STACK ADDENDUM

This document extends `docs/TECHNOLOGY_STACK.md`. No POC may delay current P0/P1 production work.

## AgroMet Intelligence Engine

Approved additions:

- ECMWF earthkit — POC for weather/climate/hydro data access/transforms/visualization patterns.
- MetPy — POC/technical library for meteorological calculations.
- xclim — POC for climate indices/extremes.
- pySTEPS — specialist POC for probabilistic precipitation nowcasting.
- xskillscore — POC/required benchmark layer for deterministic/probabilistic forecast verification.
- climpred — POC for subseasonal/seasonal ensemble skill verification.

Create a Forecast Skill Engine that records performance by variable, horizon, region, season and model. Model preference must be based on empirical skill, not reputation.

## AgroHydro / Crop Model Lab

Add:

- PyEt — POC for reference/potential evapotranspiration.
- pyfao56 — POC for FAO-56 crop coefficient, ET and daily soil water balance.
- AquaCrop — POC for water/crop/yield simulation.
- PCSE/WOFOST — POC for independent crop simulation/model comparison.
- pysheds — POC for lightweight watershed/flow/catchment derivation.
- HydroMT remains the broader hydrology candidate.

Architecture:

`observed/forecast weather -> ET0 -> soil water balance -> crop/soil model -> stress/yield scenarios -> validation against observed satellite/yield data`.

Outputs are MODELLED/ESTIMATED unless independently observed. Never label simulation as observation.

## Earth Observation Engine

Use STAC as the catalog contract.

Benchmark ODC-STAC vs StackSTAC for STAC-to-Xarray workflows. Prefer the smallest proven runtime.

Potential outputs: NDVI/EVI, surface-water/vegetation/anomaly indicators and time-window composites, with source/date/cloud/quality provenance.

## GeoIntel Service

Role separation:

- TiTiler — POC raster/COG/STAC/NetCDF/Zarr tile serving.
- TiPG — POC PostGIS OGC Features/Tiles API.
- Martin — existing dynamic vector tile candidate.
- PMTiles — existing static layer format.

Do not install all components until a real layer requires each role.

## Feature/Data Graph

Benchmark Hamilton + Ibis:

- Hamilton defines feature/dependency DAGs.
- Ibis provides backend-portable dataframe expressions across local/cloud engines.

Candidate use cases: Freight Pressure, producer-sale attractiveness, logistics congestion, weather impact and model feature lineage.

## Document intelligence

Docling remains primary. Unlimited-OCR/MinerU/Marker/ExtractThinker are benchmark/specialist candidates for difficult reports only.

## Security/engineering inheritance

AgroLog consumes shared Holding/Hermes capabilities rather than duplicating them:

- Dagger portable build/test pipeline POC;
- shared MCP/security gate;
- OpenTelemetry;
- shared Research AI Source Scout;
- Second Brain fresh context/retrieval/derived graph.

## Promotion criteria

Every POC requires a representative AgroLog dataset/task, benchmark against the current path, cost/latency/quality measurement, license/security gate, reproducibility and rollback plan.
