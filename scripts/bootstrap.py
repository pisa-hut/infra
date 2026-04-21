#!/usr/bin/env python3
"""Seed a fresh PISA deployment from the command line.

Reproduces the web UI's "Seed defaults" + per-row config/map uploads so you
don't have to click through the Resources page after a DB wipe.

Usage:
    python3 infra/scripts/bootstrap.py [--pisa-data-dir PATH]
                                       [--manager-url URL]
                                       [--postgrest-url URL]
                                       [--only rows|configs|maps|all]

Defaults:
    --pisa-data-dir  $PISA_DATA_DIR or /opt/pisa
    --manager-url    $MANAGER_URL   or http://localhost:7777/manager
    --postgrest-url  $POSTGREST_URL or http://localhost:7777/postgrest

Layout expected under --pisa-data-dir:
    config/av/{autoware,carla-agent}.yaml
    config/sim/{esmini,carla}.yaml
    map/<name>/xodr/*.xodr
    map/<name>/osm/*.osm, map/<name>/osm/map_projector_info.yaml

Zero dependencies beyond the Python standard library.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

# --- Canonical rows. Keep in sync with frontend/src/components/SeedDefaultsButton.tsx.

SEED_AVS = [
    {
        "name": "autoware",
        "image_path": {
            "apptainer": "/opt/pisa/sif/autoware.sif",
            "docker": "tonychi/autoware-wrapper:latest",
        },
        "nv_runtime": False,
        "ros_runtime": True,
        "carla_runtime": False,
    },
    {
        "name": "carla-agent",
        "image_path": {
            "apptainer": "/opt/pisa/sif/carla-agent.sif",
            "docker": "tonychi/carla-agent-wrapper:latest",
        },
        "nv_runtime": True,
        "ros_runtime": False,
        "carla_runtime": True,
    },
]

SEED_SIMULATORS = [
    {
        "name": "esmini",
        "image_path": {
            "apptainer": "/opt/pisa/sif/esmini.sif",
            "docker": "tonychi/esmini-wrapper:latest",
        },
        "nv_runtime": False,
        "ros_runtime": False,
        "carla_runtime": False,
    },
    {
        "name": "carla",
        "image_path": {
            "apptainer": "/opt/pisa/sif/carla.sif",
            "docker": "tonychi/carla-wrapper:latest",
        },
        "nv_runtime": True,
        "ros_runtime": False,
        "carla_runtime": True,
    },
]

SEED_MAPS = [{"name": "tyms"}, {"name": "frankenburg"}, {"name": "Town10HD_Opt"}]

SEED_SAMPLERS = [
    {
        "name": "grid",
        "module_path": "simcore.sampler.grid_search_sampler:GridSearchSampler",
    },
]

# av/sim configs live at config/{av|sim}/<name>.yaml
AV_CONFIG_BASENAMES = {av["name"]: f"{av['name']}.yaml" for av in SEED_AVS}
SIM_CONFIG_BASENAMES = {sim["name"]: f"{sim['name']}.yaml" for sim in SEED_SIMULATORS}


# --- Minimal HTTP helpers (stdlib only).


def _request(method: str, url: str, body: bytes | None = None, headers: dict[str, str] | None = None, timeout: int = 120) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def http_get_json(url: str) -> Any:
    status, body = _request("GET", url, headers={"Accept": "application/json"})
    if status >= 400:
        raise RuntimeError(f"GET {url} -> {status}: {body[:200]!r}")
    return json.loads(body)


def http_post_json(url: str, payload: dict[str, Any]) -> tuple[int, Any]:
    status, body = _request(
        "POST",
        url,
        body=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Prefer": "return=representation",
        },
    )
    parsed: Any
    try:
        parsed = json.loads(body) if body else None
    except json.JSONDecodeError:
        parsed = body
    return status, parsed


def http_put_bytes(url: str, data: bytes) -> int:
    status, _ = _request(
        "PUT",
        url,
        body=data,
        headers={"Content-Type": "application/octet-stream"},
    )
    return status


# --- Seeding logic.


def _existing_names(pg_url: str, table: str) -> set[str]:
    return {row["name"] for row in http_get_json(f"{pg_url}/{table}")}


def _id_by_name(pg_url: str, table: str, name: str) -> int | None:
    rows = http_get_json(f"{pg_url}/{table}?name=eq.{urllib.parse.quote(name)}&select=id")
    return rows[0]["id"] if rows else None


def seed_rows(pg_url: str) -> None:
    for table, items in (("av", SEED_AVS), ("simulator", SEED_SIMULATORS), ("map", SEED_MAPS), ("sampler", SEED_SAMPLERS)):
        existing = _existing_names(pg_url, table)
        for item in items:
            if item["name"] in existing:
                print(f"  [skip ] {table}/{item['name']} (exists)")
                continue
            status, body = http_post_json(f"{pg_url}/{table}", item)
            if 200 <= status < 300:
                print(f"  [creat] {table}/{item['name']}")
            else:
                print(f"  [ERROR] {table}/{item['name']} -> {status} {body!r}")


def upload_configs(pg_url: str, man_url: str, data_dir: Path) -> None:
    jobs = [
        ("av", AV_CONFIG_BASENAMES, "config/av"),
        ("simulator", SIM_CONFIG_BASENAMES, "config/sim"),
    ]
    for entity, name_map, subdir in jobs:
        for row_name, basename in name_map.items():
            config_path = data_dir / subdir / basename
            if not config_path.is_file():
                print(f"  [skip ] {entity}/{row_name}: {config_path} missing")
                continue
            row_id = _id_by_name(pg_url, entity, row_name)
            if row_id is None:
                print(f"  [skip ] {entity}/{row_name}: row missing (run seeding first)")
                continue
            status = http_put_bytes(f"{man_url}/{entity}/{row_id}/config", config_path.read_bytes())
            if 200 <= status < 300:
                print(f"  [up   ] {entity}/{row_name} <- {config_path}")
            else:
                print(f"  [ERROR] {entity}/{row_name} -> {status}")


def upload_map_files(pg_url: str, man_url: str, data_dir: Path) -> None:
    for spec in SEED_MAPS:
        name = spec["name"]
        row_id = _id_by_name(pg_url, "map", name)
        if row_id is None:
            print(f"  [skip ] map/{name}: row missing")
            continue
        uploaded = 0
        for bucket in ("xodr", "osm"):
            bucket_dir = data_dir / "map" / name / bucket
            if not bucket_dir.is_dir():
                continue
            for f in sorted(bucket_dir.rglob("*")):
                if not f.is_file():
                    continue
                rel = f"{bucket}/{f.relative_to(bucket_dir).as_posix()}"
                url = f"{man_url}/map/{row_id}/file/{urllib.parse.quote(rel)}"
                status = http_put_bytes(url, f.read_bytes())
                if 200 <= status < 300:
                    uploaded += 1
                else:
                    print(f"  [ERROR] map/{name}/{rel} -> {status}")
        print(f"  [up   ] map/{name}: {uploaded} file(s)")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pisa-data-dir", default=os.getenv("PISA_DATA_DIR", "/opt/pisa"))
    p.add_argument("--manager-url", default=os.getenv("MANAGER_URL", "http://localhost:7777/manager"))
    p.add_argument("--postgrest-url", default=os.getenv("POSTGREST_URL", "http://localhost:7777/postgrest"))
    p.add_argument("--only", choices=["rows", "configs", "maps", "all"], default="all")
    args = p.parse_args()

    data_dir = Path(args.pisa_data_dir).resolve()
    print(f"manager={args.manager_url} postgrest={args.postgrest_url} data_dir={data_dir}")

    if args.only in ("rows", "all"):
        print("[1/3] Seeding rows")
        seed_rows(args.postgrest_url)
    if args.only in ("configs", "all"):
        print("[2/3] Uploading configs")
        upload_configs(args.postgrest_url, args.manager_url, data_dir)
    if args.only in ("maps", "all"):
        print("[3/3] Uploading map files")
        upload_map_files(args.postgrest_url, args.manager_url, data_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
