#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from collector.climate_grid import generate_grid
from collector.ibge_malhas import extract_geometry, fetch_state_geojson
from collector.nasa_power import DEFAULT_PARAMETERS, fetch_daily


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe read-only da grade agroclimática MT")
    parser.add_argument("--spacing", type=float, default=0.75)
    parser.add_argument("--sample-points", type=int, default=3)
    parser.add_argument("--out", default="climate_grid_probe.json")
    args = parser.parse_args()

    boundary_url, payload = fetch_state_geojson(51, quality="minima")
    geometry = extract_geometry(payload)
    grid = generate_grid(geometry, spacing_deg=args.spacing)
    if len(grid) < args.sample_points:
        raise RuntimeError("grade IBGE menor que a amostra solicitada")

    sampled = []
    for point in grid[: args.sample_points]:
        observed_url, rows = fetch_daily(
            latitude=point.latitude,
            longitude=point.longitude,
            start=date(2025, 1, 1),
            end=date(2025, 1, 3),
        )
        parameters = sorted({row.parameter for row in rows})
        missing = sorted(set(DEFAULT_PARAMETERS) - set(parameters))
        if missing:
            raise RuntimeError(f"NASA POWER sem parâmetros esperados em {point.grid_id}: {missing}")
        sampled.append({
            **point.to_dict(),
            "nasa_url": observed_url,
            "rows": len(rows),
            "parameters": parameters,
            "evidence_classes": sorted({row.evidence_class for row in rows}),
            "evidence_subtypes": sorted({row.evidence_subtype for row in rows}),
        })

    report = {
        "status": "ok",
        "boundary_url": boundary_url,
        "uf_code": 51,
        "spacing_deg": args.spacing,
        "grid_points": len(grid),
        "sampled_points": sampled,
        "policy": {
            "boundary": "IBGE official state mesh",
            "grid": "regular lattice clipped to MT polygon",
            "nasa_power": "modelled_gridded_not_station_observation",
            "production_note": "agricultural-area weighting still required before statewide aggregation",
        },
    }
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
