from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
import urllib.request
from urllib.parse import urlsplit
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.logistics_gis_benchmark import BenchmarkResult, evaluate_route_case, haversine_km, summarize
from models.port_call_engine import AisStatePoint, reconstruct_port_call


def load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != "1.0":
        raise ValueError("manifest version must be 1.0")
    return data


def _timed(component: str, fn):
    started = time.perf_counter()
    try:
        metrics = fn()
        status = "PASS" if metrics.pop("_pass", True) else "FAIL"
        return BenchmarkResult(component, status, (time.perf_counter() - started) * 1000.0, metrics)
    except ModuleNotFoundError as exc:
        return BenchmarkResult(component, "SKIP", (time.perf_counter() - started) * 1000.0, {}, f"dependency missing: {exc.name}")
    except Exception as exc:
        return BenchmarkResult(component, "FAIL", (time.perf_counter() - started) * 1000.0, {}, f"{type(exc).__name__}: {exc}")


def benchmark_h3(manifest: dict[str, Any]) -> BenchmarkResult:
    def run():
        h3 = importlib.import_module("h3")
        cases = manifest["h3_cases"]
        cells = []
        for case in cases:
            cell1 = h3.latlng_to_cell(case["lat"], case["lon"], case["resolution"])
            cell2 = h3.latlng_to_cell(case["lat"], case["lon"], case["resolution"])
            if cell1 != cell2:
                raise AssertionError("H3 returned non-deterministic cell")
            if not h3.is_valid_cell(cell1):
                raise AssertionError("invalid H3 cell")
            cells.append({"id": case["id"], "cell": cell1, "resolution": h3.get_resolution(cell1)})
        return {"cases": len(cases), "cells": cells, "versions": h3.versions()}
    return _timed("h3", run)


def benchmark_pyais(manifest: dict[str, Any]) -> BenchmarkResult:
    def run():
        pyais = importlib.import_module("pyais")
        decoded = []
        for idx, sentence in enumerate(manifest["ais_nmea_samples"], start=1):
            msg = pyais.decode(sentence)
            item = msg.asdict()
            if "msg_type" not in item or "mmsi" not in item:
                raise AssertionError(f"AIS sample {idx} did not expose msg_type/mmsi")
            decoded.append({"sample": idx, "msg_type": item["msg_type"], "mmsi": item["mmsi"]})
        return {"samples": len(decoded), "decoded": decoded}
    return _timed("pyais", run)


def benchmark_pyvrp(manifest: dict[str, Any]) -> BenchmarkResult:
    def run():
        pyvrp = importlib.import_module("pyvrp")
        stop = importlib.import_module("pyvrp.stop")
        case = manifest["vrp_case"]
        model = pyvrp.Model()
        depot_xy = case["depot"]
        model.add_depot(location=model.add_location(depot_xy[0], depot_xy[1]), name="Depot")
        model.add_vehicle_type(num_available=case["vehicles"], capacity=case["capacity"])
        for idx, client in enumerate(case["clients"], start=1):
            model.add_client(
                location=model.add_location(client["x"], client["y"]),
                delivery=client["demand"],
                tw_early=client["tw_early"],
                tw_late=client["tw_late"],
                name=f"Client {idx}",
            )
        for frm in model.locations:
            for to in model.locations:
                dist = int(round(abs(frm.x - to.x) + abs(frm.y - to.y)))
                model.add_edge(frm, to, distance=dist, duration=dist)
        result = model.solve(stop=stop.MaxRuntime(case["max_runtime_seconds"]), seed=case["seed"], display=False)
        routes = list(result.best.routes())
        feasible = result.best.is_feasible()
        return {
            "_pass": bool(feasible),
            "feasible": bool(feasible),
            "routes": len(routes),
            "cost": float(result.cost()),
            "clients": len(case["clients"]),
            "vehicles_available": case["vehicles"],
        }
    return _timed("pyvrp", run)


def _post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise ValueError("benchmark endpoint must be an http(s) URL without embedded credentials")
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "AgroLogMT-benchmark/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:  # nosec B310 - benchmark URL scheme/host/credentials validated above.
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
        return json.load(response)


def benchmark_valhalla(manifest: dict[str, Any], base_url: str | None, timeout: int) -> BenchmarkResult:
    if not base_url:
        return BenchmarkResult("valhalla", "SKIP", 0.0, {}, "VALHALLA URL not supplied")

    def run():
        rows = []
        thresholds = manifest["route_thresholds"]
        for case in manifest["route_cases"]:
            payload = {
                "locations": [
                    {"lat": case["origin"]["lat"], "lon": case["origin"]["lon"]},
                    {"lat": case["destination"]["lat"], "lon": case["destination"]["lon"]},
                ],
                "costing": "truck",
                "units": "kilometers",
            }
            response = _post_json(base_url.rstrip("/") + "/route", payload, timeout)
            summary = response["trip"]["summary"]
            lower = haversine_km(
                case["origin"]["lat"], case["origin"]["lon"],
                case["destination"]["lat"], case["destination"]["lon"],
            )
            evaluated = evaluate_route_case(
                distance_km=float(summary["length"]),
                lower_bound_km=lower,
                min_ratio=float(thresholds["min_road_to_geodesic_ratio"]),
                max_ratio=float(thresholds["max_road_to_geodesic_ratio"]),
                duration_seconds=float(summary["time"]),
            )
            evaluated["id"] = case["id"]
            rows.append(evaluated)
        return {"_pass": all(row["plausible"] for row in rows), "cases": len(rows), "routes": rows}
    return _timed("valhalla", run)


def benchmark_pyosmium(pbf: Path | None) -> BenchmarkResult:
    if pbf is None:
        return BenchmarkResult("pyosmium", "SKIP", 0.0, {}, "OSM PBF not supplied")
    if not pbf.exists():
        return BenchmarkResult("pyosmium", "FAIL", 0.0, {}, f"PBF not found: {pbf}")

    def run():
        osmium = importlib.import_module("osmium")
        counts = {"node": 0, "way": 0, "relation": 0}

        class Counter(osmium.SimpleHandler):
            def node(self, _):
                counts["node"] += 1

            def way(self, _):
                counts["way"] += 1

            def relation(self, _):
                counts["relation"] += 1

        handler = Counter()
        handler.apply_file(str(pbf), locations=False)
        total = sum(counts.values())
        return {"_pass": total > 0 and counts["way"] > 0, "counts": counts, "bytes": pbf.stat().st_size}
    return _timed("pyosmium", run)


def benchmark_osmnx(manifest: dict[str, Any], allow_network: bool) -> BenchmarkResult:
    if not allow_network:
        return BenchmarkResult("osmnx", "SKIP", 0.0, {}, "network access disabled")

    def run():
        ox = importlib.import_module("osmnx")
        cfg = manifest["osmnx_probe"]
        graph = ox.graph.graph_from_point(
            (cfg["lat"], cfg["lon"]),
            dist=cfg["radius_m"],
            network_type="drive",
            simplify=True,
        )
        nodes = len(graph.nodes)
        edges = len(graph.edges)
        return {"_pass": nodes > 0 and edges > 0, "nodes": nodes, "edges": edges, "radius_m": cfg["radius_m"]}
    return _timed("osmnx", run)


def benchmark_port_call_engine() -> BenchmarkResult:
    def point(ts: str, zone: str, idx: int) -> AisStatePoint:
        return AisStatePoint(
            observed_at=ts,
            mmsi="710123456",
            port_id="SANTOS",
            zone=zone,
            quality_status="CONFIRMED_SEQUENCE",
            corroborated=True,
            observation_id=f"bench-{idx}",
        )

    def run():
        points = [
            point("2026-09-15T09:00:00+00:00", "APPROACH", 1),
            point("2026-09-15T09:02:00+00:00", "APPROACH", 2),
            point("2026-09-15T10:00:00+00:00", "ANCHORAGE", 3),
            point("2026-09-15T10:15:00+00:00", "ANCHORAGE", 4),
            point("2026-09-15T10:40:00+00:00", "ANCHORAGE", 5),
            point("2026-09-15T12:00:00+00:00", "CHANNEL", 6),
            point("2026-09-15T12:02:00+00:00", "CHANNEL", 7),
            point("2026-09-15T12:20:00+00:00", "BERTH", 8),
            point("2026-09-15T12:30:00+00:00", "BERTH", 9),
        ]
        first = reconstruct_port_call(port_id="SANTOS", ais_points=points)
        second = reconstruct_port_call(port_id="SANTOS", ais_points=reversed(points))
        states_first = [event.state for event in first.events]
        states_second = [event.state for event in second.events]
        expected = {"APROXIMACAO", "FUNDEADO", "AGUARDANDO", "MANOBRA", "ATRACADO"}
        same = first.to_dict() == second.to_dict()
        passed = states_first == states_second and expected.issubset(set(states_first)) and same
        return {
            "_pass": passed,
            "states": states_first,
            "idempotent_under_input_order": same,
            "waiting_hours": first.waiting_hours,
        }
    return _timed("port_call_engine", run)


def main() -> int:
    parser = argparse.ArgumentParser(description="AgroLog logistics/GIS/maritime benchmark gate")
    parser.add_argument("--manifest", default="benchmarks/logistics_gis/manifest.v1.json")
    parser.add_argument("--out", default="outputs/benchmarks/logistics-gis.json")
    parser.add_argument("--valhalla-url", default=None)
    parser.add_argument("--osm-pbf", default=None)
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Treat SKIP as release-blocking")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    manifest = load_manifest(ROOT / args.manifest)
    results = [
        benchmark_port_call_engine(),
        benchmark_h3(manifest),
        benchmark_pyais(manifest),
        benchmark_pyvrp(manifest),
        benchmark_valhalla(manifest, args.valhalla_url, args.timeout),
        benchmark_pyosmium(Path(args.osm_pbf) if args.osm_pbf else None),
        benchmark_osmnx(manifest, args.allow_network),
    ]
    summary = summarize(results, require_no_skips=args.strict)
    report = {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest": args.manifest,
        "strict": args.strict,
        "summary": summary,
        "results": [row.to_dict() for row in results],
    }
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for row in results:
        suffix = f" — {row.reason}" if row.reason else ""
        print(f"[{row.status}] {row.component}{suffix}")
    print(f"AGROLOG LOGISTICS GIS BENCHMARK: {summary['status']}")
    print(f"report={out}")
    if args.strict:
        return 0 if summary["status"] == "PASS" else 1
    return 0 if summary["status"] in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
