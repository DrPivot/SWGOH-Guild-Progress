from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
CHARACTERS_JSON_PATH = ROOT_DIR / "data" / "swgoh_gg" / "characters.json"
SHIPS_JSON_PATH = ROOT_DIR / "data" / "swgoh_gg" / "ships.json"
ERA_CATALOG_PATH = ROOT_DIR / "data" / "unit_era_catalog.csv"
RELIC_BENCHMARKS_PATH = ROOT_DIR / "data" / "relic_benchmarks.csv"
OUTPUT_CSV_PATH = ROOT_DIR / "data" / "unit_list.csv"

OUTPUT_COLUMNS = [
    "BaseID",
    "Name",
    "combat_type",
    "alignment",
    "role",
    "categories",
    "ability_classes",
    "image",
    "ship",
    "era",
    "unit_relic_all",
    "unit_relic_guilds_100",
    "unit_relic_kyber_1000",
]


def load_json_records(file_path: Path) -> list[dict[str, object]]:
    with file_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_csv_lookup(file_path: Path, key_field: str) -> dict[str, dict[str, str]]:
    if not file_path.exists():
        raise FileNotFoundError(f"Required CSV file not found: {file_path}")

    with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return {
            str(row.get(key_field, "")).strip(): {key: (value or "") for key, value in row.items()}
            for row in reader
            if str(row.get(key_field, "")).strip()
        }


def normalize_text_list(value: object) -> str:
    if not value:
        return ""
    if not isinstance(value, list):
        return str(value).strip()
    return "|".join(str(item).strip() for item in value if str(item).strip())


def build_unit_record(unit_data: dict[str, object], default_ship: str = "") -> dict[str, object]:
    base_id = str(unit_data.get("base_id", "")).strip()
    name = str(unit_data.get("name", "")).strip()
    if not base_id or not name:
        raise ValueError(f"Unit record missing BaseID or Name: {unit_data}")

    combat_type = unit_data.get("combat_type", "")
    return {
        "BaseID": base_id,
        "Name": name,
        "combat_type": combat_type,
        "alignment": str(unit_data.get("alignment", "") or "").strip(),
        "role": str(unit_data.get("role", "") or "").strip(),
        "categories": normalize_text_list(unit_data.get("categories", [])),
        "ability_classes": normalize_text_list(unit_data.get("ability_classes", [])),
        "image": str(unit_data.get("image", "") or "").strip(),
        "ship": str(unit_data.get("ship", default_ship) or "").strip(),
    }


def build_base_unit_records() -> list[dict[str, object]]:
    characters = load_json_records(CHARACTERS_JSON_PATH)
    ships = load_json_records(SHIPS_JSON_PATH)

    records: list[dict[str, object]] = []
    seen_base_ids: set[str] = set()

    for unit_data in characters:
        record = build_unit_record(unit_data)
        base_id = str(record["BaseID"])
        if base_id in seen_base_ids:
            raise ValueError(f"Duplicate BaseID detected in base sources: {base_id}")
        seen_base_ids.add(base_id)
        records.append(record)

    for unit_data in ships:
        record = build_unit_record(unit_data, default_ship="")
        base_id = str(record["BaseID"])
        if base_id in seen_base_ids:
            raise ValueError(f"Duplicate BaseID detected in base sources: {base_id}")
        seen_base_ids.add(base_id)
        records.append(record)

    return records


def enrich_unit_records(
    unit_records: list[dict[str, object]],
    era_lookup: dict[str, dict[str, str]],
    relic_lookup: dict[str, dict[str, str]],
) -> list[dict[str, object]]:
    enriched_records: list[dict[str, object]] = []

    for unit_record in unit_records:
        base_id = str(unit_record["BaseID"])
        era_row = era_lookup.get(base_id, {})
        relic_row = relic_lookup.get(base_id, {})

        enriched_records.append(
            {
                **unit_record,
                "era": era_row.get("era", ""),
                "unit_relic_all": relic_row.get("unit_relic_all", ""),
                "unit_relic_guilds_100": relic_row.get("unit_relic_guilds_100", ""),
                "unit_relic_kyber_1000": relic_row.get("unit_relic_kyber_1000", ""),
            }
        )

    return enriched_records


def sort_unit_records(unit_records: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(
        unit_records,
        key=lambda row: (
            int(row.get("combat_type") or 999),
            str(row.get("BaseID", "")).casefold(),
        ),
    )


def write_unit_catalog(file_path: Path, unit_records: list[dict[str, object]]) -> None:
    with file_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in unit_records:
            writer.writerow({column: row.get(column, "") for column in OUTPUT_COLUMNS})


def create_unit_list(output_csv_path: Path = OUTPUT_CSV_PATH) -> list[dict[str, object]]:
    unit_records = build_base_unit_records()
    era_lookup = load_csv_lookup(ERA_CATALOG_PATH, "BaseID")
    relic_lookup = load_csv_lookup(RELIC_BENCHMARKS_PATH, "BaseID")

    enriched_records = enrich_unit_records(unit_records, era_lookup, relic_lookup)
    sorted_records = sort_unit_records(enriched_records)
    write_unit_catalog(output_csv_path, sorted_records)
    return sorted_records


def main() -> None:
    unit_records = create_unit_list()
    character_count = sum(1 for row in unit_records if int(row["combat_type"]) == 1)
    ship_count = sum(1 for row in unit_records if int(row["combat_type"]) == 2)
    relic_count = sum(1 for row in unit_records if row["unit_relic_all"])
    era_count = sum(1 for row in unit_records if row["era"])

    print(f"Wrote {len(unit_records)} rows to {OUTPUT_CSV_PATH}")
    print(f"Characters: {character_count}")
    print(f"Ships: {ship_count}")
    print(f"Units with era: {era_count}")
    print(f"Units with relic benchmark: {relic_count}")


if __name__ == "__main__":
    main()