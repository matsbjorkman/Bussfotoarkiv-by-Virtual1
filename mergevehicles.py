from pathlib import Path
import json
import sys


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def vehicle_sort_key(v: dict):
    name_key = str(v.get("opName") or v.get("type") or "").lower()
    variant_key = str(v.get("variant", "")).lower()
    number_type = str(v.get("numberType", "numeric")).lower()

    if number_type == "numeric":
        return (
            str(v.get("kind", "")).lower(),
            name_key,
            0,
            v.get("sortNumber") if v.get("sortNumber") is not None else 0,
            variant_key,
            str(v.get("key", "")).lower(),
        )

    return (
        str(v.get("kind", "")).lower(),
        name_key,
        1,
        str(v.get("sortText") or v.get("n") or "").lower(),
        variant_key,
        str(v.get("key", "")).lower(),
    )


def main():
    if len(sys.argv) < 2:
        print("Användning:")
        print('python merge_vehicles.py "SAJTMAPP"')
        sys.exit(1)

    site_dir = Path(sys.argv[1]).resolve()
    data_dir = site_dir / "data"

    if not data_dir.exists() or not data_dir.is_dir():
        print(f"Fel: datamappen finns inte: {data_dir}")
        sys.exit(1)

    part_files = sorted(
        p for p in data_dir.glob("*-vehicles.json")
        if p.name.lower() != "vehicles.json"
    )

    if not part_files:
        print("Inga delfiler hittades.")
        print(f"Sökte i: {data_dir}")
        sys.exit(1)

    merged = []
    seen_keys = {}
    duplicates = []

    for path in part_files:
        try:
            data = load_json(path)
        except Exception as e:
            print(f"[FEL] Kunde inte läsa {path.name}: {e}")
            continue

        if not isinstance(data, list):
            print(f"[HOPPAR ÖVER] {path.name} är inte en JSON-array.")
            continue

        for vehicle in data:
            key = vehicle.get("key")
            if not key:
                duplicates.append({
                    "reason": "saknar key",
                    "file": path.name,
                })
                continue

            if key in seen_keys:
                duplicates.append({
                    "reason": "dublett",
                    "key": key,
                    "firstFile": seen_keys[key],
                    "duplicateFile": path.name,
                })
                continue

            seen_keys[key] = path.name
            merged.append(vehicle)

    merged.sort(key=vehicle_sort_key)

    out_file = data_dir / "vehicles.json"
    write_json(out_file, merged)

    summary = {
        "partFiles": [p.name for p in part_files],
        "partFileCount": len(part_files),
        "vehicleCount": len(merged),
        "duplicateCount": len(duplicates),
        "duplicates": duplicates,
    }

    summary_file = data_dir / "vehicles-merge-summary.json"
    write_json(summary_file, summary)

    print(f"Klart: slog ihop {len(part_files)} filer.")
    print(f"Skrev: {out_file}")
    print(f"Antal fordon: {len(merged)}")

    if duplicates:
        print(f"Dubbletter/problem: {len(duplicates)} st")
        print(f"Se: {summary_file}")
    else:
        print("Inga dubletter hittades.")
        print(f"Skrev också: {summary_file}")


if __name__ == "__main__":
    main()