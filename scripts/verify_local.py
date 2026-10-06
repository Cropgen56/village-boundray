"""
verify_local.py
---------------
End-to-end local check that the app starts against the private GCS bucket.

Runs the real FastAPI app in-process (including its startup, which downloads
mh1/mh2 from Cloud Storage) and checks:
  1. FastAPI starts successfully
  2. mh1.geojson is downloaded from GCS and parsed
  3. mh2.geojson is downloaded from GCS and parsed
  4. Both datasets are merged and indexed
  5. GET /docs works (and the OpenAPI schema still exposes /boundary/)
  6. GET /boundary/ returns the same results as before

Prerequisites (from the project root):
    gcloud auth application-default login
    pip install -r requirements-dev.txt
    cp .env.example .env

Run:
    python scripts/verify_local.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # installed with uvicorn[standard]

load_dotenv(ROOT / ".env")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import GCS_BUCKET_NAME, GCS_GEOJSON_OBJECTS  # noqa: E402
from app.main import app  # noqa: E402
from app.services.data_loader import geo_store  # noqa: E402

# A known point (Dhanki village, Umarkhed taluka, Yavatmal district) and
# the properties /boundary/ returned for it before the move to GCS.
LAT, LNG = 19.570304, 77.8438
EXPECTED = {
    "village": {
        "level": "village", "name": "Dhanki", "taluka": "Umarkhed",
        "district": "Yavatmal", "state": "Maharashtra",
        "census_code": "275100408601793000",
    },
    "taluka": {
        "level": "taluka", "taluka": "Umarkhed", "district": "Yavatmal",
        "state": "Maharashtra", "queried_village": "Dhanki",
        "queried_village_code": "275100408601793000",
    },
    "district": {
        "level": "district", "district": "Yavatmal", "state": "Maharashtra",
        "queried_village": "Dhanki",
        "queried_village_code": "275100408601793000",
    },
}

failures = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global failures
    failures += not ok
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))


def main() -> int:
    try:
        client = TestClient(app)
        client.__enter__()  # runs the lifespan: GCS download + data load
    except Exception as exc:
        check("1. FastAPI starts", False, f"{type(exc).__name__}: {exc}")
        return 1
    check("1. FastAPI starts", True)

    try:
        for n, object_path in enumerate(GCS_GEOJSON_OBJECTS.values(), start=2):
            uri = f"gs://{GCS_BUCKET_NAME}/{object_path}"
            count = geo_store.source_counts.get(uri, 0)
            check(f"{n}. {uri} downloaded", count > 0, f"{count} features")

        check(
            "4. Datasets loaded",
            geo_store.is_loaded and len(geo_store.village_attrs) == sum(geo_store.source_counts.values()),
            f"{len(geo_store.village_attrs)} villages, {len(geo_store.taluka_geoms)} talukas, "
            f"{len(geo_store.district_geoms)} districts",
        )

        docs = client.get("/docs")
        params = [
            p["name"]
            for p in client.get("/openapi.json").json()["paths"]["/boundary/"]["get"]["parameters"]
        ]
        check("5. GET /docs", docs.status_code == 200 and params == ["lat", "lng", "level"],
              f"status {docs.status_code}, /boundary/ params {params}")

        for level, expected in EXPECTED.items():
            r = client.get("/boundary/", params={"lat": LAT, "lng": LNG, "level": level})
            body = r.json() if r.status_code == 200 else {}
            ok = (
                r.status_code == 200
                and r.headers["content-type"] == "application/geo+json"
                and body.get("type") == "Feature"
                and body.get("geometry", {}).get("type") in {"Polygon", "MultiPolygon"}
                and body.get("properties") == expected
            )
            check(f"6. GET /boundary/ level={level}", ok,
                  f"status {r.status_code}, {len(r.content)} bytes")

        r = client.get("/boundary/", params={"lat": 10, "lng": 10})
        check("6. GET /boundary/ outside Maharashtra -> 404", r.status_code == 404)
        r = client.get("/boundary/", params={"lat": LAT, "lng": LNG, "level": "state"})
        check("6. GET /boundary/ invalid level -> 422", r.status_code == 422)
    finally:
        client.__exit__(None, None, None)

    print("\nAll checks passed." if not failures else f"\n{failures} check(s) failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
