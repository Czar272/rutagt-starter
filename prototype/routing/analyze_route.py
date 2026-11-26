import json
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

from rutagt.core.snapshots import resolve_snapshot

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_ROOT = PROJECT_ROOT / "data" / "raw"
STOPS_LAYER = "muniguate/tubus_stops_2025.geojson"
ROUTES_LAYER = "muniguate/tubus_routes_2025.geojson"

OFFICIAL_FILE = (
    PROJECT_ROOT / "prototype" / "routing" / "data" / "route_801_official.json"
)


def raw_file(layer: str) -> Path:
    """Capa del snapshot crudo vigente (`data/raw/LATEST`, ADR-0032)."""
    return resolve_snapshot(RAW_ROOT) / layer


ROUTE_CODE = "801"


def load_json(path):
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def normalize_text(value):
    if not value:
        return ""

    value = unicodedata.normalize("NFKD", str(value))
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.lower()

    replacements = {
        "avenida": "av",
        "calzada": "calz",
        "bulevar": "blvr",
        "colonia": "col",
        "condominio": "cond",
        "periferico": "periferico",
    }

    for old, new in replacements.items():
        value = re.sub(rf"\b{old}\b", new, value)

    value = re.sub(r"[^\w\s]", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def extract_stop_code(name):
    if not name:
        return None

    match = re.search(r"\b(\d{2,3})\b", str(name))

    if not match:
        return None

    return match.group(1).zfill(3)


def get_route_stops(data):
    return [
        feature
        for feature in data["features"]
        if str(feature["properties"].get("Codigoruta")) == ROUTE_CODE
    ]


def address_similarity(official_address, geojson_address):
    left = normalize_text(official_address)
    right = normalize_text(geojson_address)

    return SequenceMatcher(None, left, right).ratio()


def candidate_score(official, feature):
    properties = feature["properties"]

    official_code = official["stop_code"]
    geojson_code = extract_stop_code(properties.get("Nombre_lug"))

    score = 0.0
    reasons = []

    if geojson_code == official_code:
        score += 0.55
        reasons.append("stop_code")

    if properties.get("Zona") == official["zone"]:
        score += 0.10
        reasons.append("zone")

    similarity = address_similarity(
        official["address"],
        properties.get("Direccion"),
    )

    score += similarity * 0.35

    if similarity >= 0.75:
        reasons.append("address")

    return score, similarity, reasons


def classify(score, code_matches, similarity, zone_matches):
    if code_matches and similarity >= 0.75:
        return "EXACT"

    if code_matches and score >= 0.70:
        return "LIKELY"

    if not code_matches and zone_matches and similarity >= 0.70:
        return "ADDRESS_MATCH"

    if score >= 0.40:
        return "AMBIGUOUS"

    return "UNMATCHED"


def reconcile(official_stops, geojson_stops):
    results = []

    for official in official_stops:
        candidates = []

        for feature in geojson_stops:
            score, similarity, reasons = candidate_score(
                official,
                feature,
            )

            properties = feature["properties"]
            geojson_code = extract_stop_code(properties.get("Nombre_lug"))
            zone_matches = properties.get("Zona") == official["zone"]

            candidates.append(
                {
                    "feature": feature,
                    "score": score,
                    "similarity": similarity,
                    "reasons": reasons,
                    "code_matches": (geojson_code == official["stop_code"]),
                    "zone_matches": zone_matches,
                }
            )

        candidates.sort(
            key=lambda candidate: candidate["score"],
            reverse=True,
        )

        best = candidates[0]

        classification = classify(
            best["score"],
            best["code_matches"],
            best["similarity"],
            best["zone_matches"],
        )

        results.append(
            {
                "official": official,
                "candidate": best,
                "classification": classification,
            }
        )

    return results


def print_geojson_summary(stops):
    names = [stop["properties"].get("Nombre_lug") for stop in stops]

    duplicates = {name: count for name, count in Counter(names).items() if count > 1}

    print(f"Registros GeoJSON: {len(stops)}")
    print(f"Nombres duplicados: {len(duplicates)}")

    for name, count in sorted(duplicates.items()):
        print(f"  - {name}: {count}")


def print_reconciliation(results):
    print()
    print("RECONCILIACION")
    print("-" * 80)

    counts = Counter()

    for result in results:
        official = result["official"]
        candidate = result["candidate"]
        feature = candidate["feature"]
        properties = feature["properties"]

        classification = result["classification"]
        counts[classification] += 1

        print(
            f"#{official['stop_code']} "
            f"seq={official['sequence']:02d} "
            f"-> {classification:9} | "
            f"FID={properties.get('FID')} | "
            f"{properties.get('Nombre_lug')} | "
            f"score={candidate['score']:.3f} | "
            f"address={candidate['similarity']:.3f}"
        )

    print()
    print("RESUMEN")
    print("-" * 80)

    for classification in (
        "EXACT",
        "LIKELY",
        "ADDRESS_MATCH",
        "AMBIGUOUS",
        "UNMATCHED",
    ):
        print(f"{classification:9}: {counts[classification]}")


def print_candidate_usage(results, geojson_stops):
    print()
    print("USO DE REGISTROS GEOJSON")
    print("-" * 80)

    used_fids = []

    for result in results:
        if result["classification"] in ("UNMATCHED", "AMBIGUOUS"):
            continue

        feature = result["candidate"]["feature"]
        fid = feature["properties"].get("FID")
        used_fids.append(fid)

    duplicated_fids = {
        fid: count for fid, count in Counter(used_fids).items() if count > 1
    }

    all_fids = {feature["properties"].get("FID") for feature in geojson_stops}

    used_unique_fids = set(used_fids)
    unused_fids = all_fids - used_unique_fids

    print(f"FIDs utilizados: {len(used_unique_fids)}")
    print(f"FIDs usados multiples veces: {len(duplicated_fids)}")

    for fid, count in sorted(duplicated_fids.items()):
        print(f"  - FID {fid}: {count} veces")

    print(f"FIDs sin utilizar: {len(unused_fids)}")

    for feature in geojson_stops:
        properties = feature["properties"]
        fid = properties.get("FID")

        if fid not in unused_fids:
            continue

        print(
            f"  - FID={fid} | "
            f"{properties.get('Nombre_lug')} | "
            f"{properties.get('Direccion')}"
        )


def main():
    geojson = load_json(raw_file(STOPS_LAYER))
    official = load_json(OFFICIAL_FILE)

    geojson_stops = get_route_stops(geojson)
    official_stops = official["stops"]

    print(f"Ruta TuBus {ROUTE_CODE}")
    print(f"Paradas oficiales: {len(official_stops)}")

    print_geojson_summary(geojson_stops)

    results = reconcile(
        official_stops,
        geojson_stops,
    )

    print_reconciliation(results)
    print_candidate_usage(
        results,
        geojson_stops,
    )


if __name__ == "__main__":
    main()
