from pathlib import Path
import json
import re
import sys

OPERATOR_RULES = {
    "nobina": {
        "displayName": "Nobina",
        "aliases": ["nobina", "swebus"],
        "formerNames": ["Swebus"],
    },
    "keolis": {
        "displayName": "Keolis",
        "aliases": ["keolis", "busslink"],
        "formerNames": ["Busslink"],
    },
    "transdev": {
        "displayName": "Transdev",
        "aliases": ["transdev", "veolia", "connex", "linjebuss"],
        "formerNames": ["Veolia", "Connex", "Linjebuss"],
    },
}

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

# Buss:
# - operatör först
# - sedan fordons-ID som kan vara numeriskt eller alfanumeriskt
# - sist ev. bildordning: -1, -2, ...
#
# Exempel som ska fungera:
# nobina614-1.jpg
# goranssonsthx24r-1.jpg
# bergkvarabc123d-2.jpg
#
# Fordons-ID måste innehålla minst en siffra för att undvika att operatörsnamnet slukar allt.

BUS_NUMERIC_RE = re.compile(
    r"^([a-zA-ZåäöÅÄÖ_-]+?)(\d{1,5})(?:-(\d+))?\.(jpe?g|png|webp|gif)$",
    re.I,
)

BUS_DOTTED_ALPHA_RE = re.compile(
    r"^([a-zA-ZåäöÅÄÖ_-]+)\.([a-zA-Z0-9]+)(?:-(\d+))?\.(jpe?g|png|webp|gif)$",
    re.I,
)

RAIL_NUM_TYPE_RE = re.compile(r"^(\d{1,5})-([a-zA-Z0-9]+)-(\d+)\.(jpe?g|png|webp|gif)$", re.I)
RAIL_TYPE_NUM_RE = re.compile(r"^([a-zA-Z0-9]+)-(\d{1,5})-(\d+)\.(jpe?g|png|webp|gif)$", re.I)


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9åäö]+", "", value.lower())


def title_case(value: str) -> str:
    value = re.sub(r"[_-]+", " ", value).strip()
    return " ".join(part[:1].upper() + part[1:].lower() for part in value.split())


def canonical_bus_operator(raw_operator: str) -> dict:
    key = slugify(raw_operator)
    for rule in OPERATOR_RULES.values():
        if any(slugify(alias) == key for alias in rule["aliases"]):
            return {
                "key": slugify(rule["displayName"]),
                "displayName": rule["displayName"],
                "rawName": title_case(raw_operator),
                "formerNames": rule.get("formerNames", []),
            }
    return {
        "key": key,
        "displayName": title_case(raw_operator),
        "rawName": title_case(raw_operator),
        "formerNames": [],
    }


def normalize_vehicle_id(value: str):
    value = value.strip()
    if value.isdigit():
        n_num = int(value)
        return {
            "n": n_num,
            "numberType": "numeric",
            "sortNumber": n_num,
            "sortText": f"{n_num:06d}",
            "th": (n_num // 1000) * 1000,
            "hd": (n_num // 100) * 100,
        }

    n_text = value.upper()
    return {
        "n": n_text,
        "numberType": "alphanumeric",
        "sortNumber": None,
        "sortText": n_text,
        "th": None,
        "hd": None,
    }


def parse_bus(filename: str):
    # 1. "Övriga"-fall med punkt:
    # goranssons.pxt16r-1.jpg
    # goranssons.klo156-1.jpg
    dotted = BUS_DOTTED_ALPHA_RE.match(filename)
    if dotted:
        raw_operator, vehicle_id, image_order, _ext = dotted.groups()
        canon = canonical_bus_operator(raw_operator)
        vehicle_id = vehicle_id.upper()

        return {
            "kind": "bus",
            "op": canon["key"],
            "opName": canon["displayName"],
            "raw": canon["rawName"],
            "former": canon["formerNames"],
            "type": "",
            "n": vehicle_id,
            "numberType": "alphanumeric",
            "sortNumber": None,
            "sortText": vehicle_id,
            "ord": int(image_order or 1),
            "th": None,
            "hd": None,
        }

    # 2. Vanliga numeriska bussar:
    # vargarda105-1.jpg
    # nobina614-1.jpg
    numeric = BUS_NUMERIC_RE.match(filename)
    if numeric:
        raw_operator, number, image_order, _ext = numeric.groups()
        canon = canonical_bus_operator(raw_operator)
        vehicle_number = int(number)

        return {
            "kind": "bus",
            "op": canon["key"],
            "opName": canon["displayName"],
            "raw": canon["rawName"],
            "former": canon["formerNames"],
            "type": "",
            "n": vehicle_number,
            "numberType": "numeric",
            "sortNumber": vehicle_number,
            "sortText": f"{vehicle_number:06d}",
            "ord": int(image_order or 1),
            "th": (vehicle_number // 1000) * 1000,
            "hd": (vehicle_number // 100) * 100,
        }

    return None

def parse_rail(filename: str, forced_kind: str = ""):
    m = RAIL_NUM_TYPE_RE.match(filename)
    if m:
        number, vehicle_type, image_order, _ext = m.groups()
    else:
        m = RAIL_TYPE_NUM_RE.match(filename)
        if not m:
            return None
        vehicle_type, number, image_order, _ext = m.groups()

    type_upper = vehicle_type.upper()
    inferred_kind = forced_kind or ("train" if type_upper.startswith(("X", "Y")) else "tram")
    n_num = int(number)

    return {
        "kind": inferred_kind,
        "op": "",
        "opName": "",
        "raw": "",
        "former": [],
        "type": type_upper,
        "n": n_num,
        "numberType": "numeric",
        "sortNumber": n_num,
        "sortText": f"{n_num:06d}",
        "ord": int(image_order or 1),
        "th": (n_num // 1000) * 1000,
        "hd": (n_num // 100) * 100,
    }


def detect_forced_kind(rel_path: str) -> str:
    lower = rel_path.lower().replace("\\", "/")
    parts = lower.split("/")

    if any(part in ("pendeltag", "pendeltåg") for part in parts):
        return "train"
    if any(part in ("sparvagn", "spårvagn", "tram") for part in parts):
        return "tram"
    return ""


def extract_variant(rel_path: str) -> str:
    parts = rel_path.replace("\\", "/").split("/")
    # Exempel:
    # transdev/connex1415-1.jpg -> ingen variant
    # transdev/Generation 1/connex1415-1.jpg -> variant = Generation 1
    # transdev/Generation 1/special/connex1415-1.jpg -> fortfarande variant = Generation 1
    if len(parts) >= 3:
        return parts[1]
    return ""


def parse_record(rel_path: str):
    rel_posix = rel_path.replace("\\", "/")
    filename = Path(rel_posix).name

    forced_kind = detect_forced_kind(rel_posix)
    base = parse_rail(filename, forced_kind) or parse_bus(filename)
    if not base:
        return None

    variant = extract_variant(rel_posix)

    return {
        **base,
        "file": rel_posix,
        "variant": variant,
    }


def build_vehicle_groups(records):
    grouped = {}

    for rec in records:
        variant_slug = slugify(rec.get("variant", ""))

        if rec["kind"] == "bus":
            vehicle_id_key = slugify(str(rec["n"]))
            key = f'bus|{rec["op"]}|{vehicle_id_key}'
            if variant_slug:
                key += f'|{variant_slug}'
        else:
            key = f'{rec["kind"]}|{slugify(rec["type"])}|{rec["n"]}'
            if variant_slug:
                key += f'|{variant_slug}'

        grouped.setdefault(key, []).append(rec)

    vehicles = []
    for key, images in grouped.items():
        images.sort(key=lambda x: (x["ord"], x["file"]))
        first = images[0]

        vehicle = {
            "key": key,
            "kind": first["kind"],
            "n": first["n"],
            "numberType": first.get("numberType", "numeric"),
            "sortNumber": first.get("sortNumber"),
            "sortText": first.get("sortText", str(first["n"])),
            "th": first["th"],
            "hd": first["hd"],
            "images": [[img["file"], img["ord"]] for img in images],
            "variant": first.get("variant", ""),
        }

        if first["kind"] == "bus":
            vehicle["op"] = first["op"]
            vehicle["opName"] = first["opName"]
            if first["raw"] and first["raw"] != first["opName"]:
                vehicle["raw"] = first["raw"]
            if first["former"]:
                vehicle["former"] = first["former"]
        else:
            vehicle["type"] = first["type"]

        vehicles.append(vehicle)

    def vehicle_sort_key(v):
        name_key = (v.get("opName") or v.get("type") or "").lower()
        variant_key = v.get("variant", "").lower()

        if v.get("numberType") == "numeric":
            return (
                v["kind"],
                name_key,
                0,
                v.get("sortNumber") if v.get("sortNumber") is not None else 0,
                variant_key,
            )

        return (
            v["kind"],
            name_key,
            1,
            str(v.get("sortText", v.get("n", ""))).lower(),
            variant_key,
        )

    vehicles.sort(key=vehicle_sort_key)
    return vehicles


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def main():
    if len(sys.argv) < 3:
        print("Användning:")
        print('python buildvehicles.py "KÄLLMAPP" "SAJTMAPP"')
        sys.exit(1)

    source_dir = Path(sys.argv[1]).resolve()
    site_dir = Path(sys.argv[2]).resolve()

    if not source_dir.exists() or not source_dir.is_dir():
        print("Fel: källmappen finns inte eller är inte en katalog.")
        sys.exit(1)

    data_dir = site_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    records = []
    skipped = []

    source_prefix = source_dir.name.lower()

    for src in source_dir.rglob("*"):
        if not src.is_file():
            continue
        if src.suffix.lower() not in IMAGE_EXTS:
            continue
        if "thumbs" in src.parts or "data" in src.parts:
            continue

        rel_inside_source = src.relative_to(source_dir).as_posix()
        rel_path = f"{source_prefix}/{rel_inside_source}"
        record = parse_record(rel_path)

        if record is None:
            skipped.append(rel_path)
            continue

        records.append(record)

    vehicles = build_vehicle_groups(records)

    out_file = data_dir / f"{slugify(source_dir.name)}-vehicles.json"
    write_json(out_file, vehicles)

    summary_file = data_dir / f"{slugify(source_dir.name)}-summary.json"
    write_json(summary_file, {
        "sourceDir": str(source_dir),
        "vehicleCount": len(vehicles),
        "imageCount": len(records),
        "skipped": skipped,
    })

    print(f"Klart: {len(vehicles)} fordon, {len(records)} bilder.")
    print(f"Skrev: {out_file}")
    print(f"Skrev: {summary_file}")

    if skipped:
        print("Överhoppade filer:")
        for item in skipped[:50]:
            print(" -", item)
        if len(skipped) > 50:
            print(" ...")


if __name__ == "__main__":
    main()