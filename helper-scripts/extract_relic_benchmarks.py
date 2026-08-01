from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
import re


ROOT_DIR = Path(__file__).resolve().parents[1]
CHARACTERS_JSON_PATH = ROOT_DIR / "data" / "swgoh_gg" / "characters.json"
RAW_OUTPUT_CSV_PATH = ROOT_DIR / "data" / "relic_player_data_raw.csv"
BENCHMARK_OUTPUT_CSV_PATH = ROOT_DIR / "data" / "relic_benchmarks.csv"

SOURCE_FILES = {
    "all": ROOT_DIR / "data" / "swgoh_gg" / "relics_all.html",
    "guilds_100": ROOT_DIR / "data" / "swgoh_gg" / "relics_guilds_100.html",
    "kyber_1000": ROOT_DIR / "data" / "swgoh_gg" / "relics_kyber_1000.html",
}

RELIC_COLUMNS = [f"r{level}" for level in range(1, 11)]
BENCHMARK_COLUMNS = {
    "all": "unit_relic_all",
    "guilds_100": "unit_relic_guilds_100",
    "kyber_1000": "unit_relic_kyber_1000",
}
UNIT_SLUG_PATTERN = re.compile(r"/units/([^/]+)/")


@dataclass(frozen=True)
class ParsedTableRow:
    base_id_hint: str | None
    href: str | None
    cells: list[str]


@dataclass
class CharacterLookups:
    name_by_base_id: dict[str, str]
    slug_to_base_id: dict[str, str]
    name_to_base_ids: dict[str, list[str]]


class RelicTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[ParsedTableRow] = []
        self.found_target_table = False
        self.in_target_table = False
        self.table_depth = 0
        self.in_tbody = False
        self.in_row = False
        self.in_cell = False
        self.current_row_base_id: str | None = None
        self.current_row_href: str | None = None
        self.current_row_cells: list[str] = []
        self.current_cell_parts: list[str] = []
        self.current_cell_datetime: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        class_value = attrs_dict.get("class", "") or ""

        if tag == "table":
            if self.in_target_table:
                self.table_depth += 1
                return

            if not self.found_target_table and "stat-table" in class_value:
                self.found_target_table = True
                self.in_target_table = True
                self.table_depth = 1
            return

        if not self.in_target_table:
            return

        if tag == "tbody":
            self.in_tbody = True
            return

        if not self.in_tbody:
            return

        if tag == "tr":
            self.in_row = True
            self.current_row_base_id = None
            self.current_row_href = None
            self.current_row_cells = []
            return

        if not self.in_row:
            return

        if tag == "td":
            self.in_cell = True
            self.current_cell_parts = []
            self.current_cell_datetime = None
            return

        if not self.in_cell:
            return

        if tag == "a":
            base_id_hint = attrs_dict.get("data-unit-def-tooltip-app")
            if base_id_hint:
                self.current_row_base_id = base_id_hint.strip()
            href = attrs_dict.get("href")
            if href:
                self.current_row_href = href.strip()
            return

        if tag == "time":
            datetime_value = attrs_dict.get("datetime")
            if datetime_value:
                self.current_cell_datetime = datetime_value.strip()

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self.in_target_table:
            self.table_depth -= 1
            if self.table_depth <= 0:
                self.in_target_table = False
                self.in_tbody = False
            return

        if not self.in_target_table:
            return

        if tag == "tbody":
            self.in_tbody = False
            return

        if not self.in_tbody:
            return

        if tag == "td" and self.in_cell:
            cell_text = self.current_cell_datetime or normalize_text(" ".join(self.current_cell_parts))
            self.current_row_cells.append(cell_text)
            self.current_cell_parts = []
            self.current_cell_datetime = None
            self.in_cell = False
            return

        if tag == "tr" and self.in_row:
            if self.current_row_cells:
                self.rows.append(
                    ParsedTableRow(
                        base_id_hint=self.current_row_base_id,
                        href=self.current_row_href,
                        cells=self.current_row_cells,
                    )
                )
            self.in_row = False
            self.current_row_base_id = None
            self.current_row_href = None
            self.current_row_cells = []

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            cleaned = normalize_text(data)
            if cleaned:
                self.current_cell_parts.append(cleaned)


def normalize_text(value: str) -> str:
    return " ".join(value.split())


def extract_slug_from_url(url: str | None) -> str | None:
    if not url:
        return None
    match = UNIT_SLUG_PATTERN.search(url)
    if not match:
        return None
    return match.group(1).strip().casefold()


def load_characters_json() -> list[dict[str, object]]:
    with CHARACTERS_JSON_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_character_lookups() -> CharacterLookups:
    name_by_base_id: dict[str, str] = {}
    slug_to_base_id: dict[str, str] = {}
    name_to_base_ids: dict[str, list[str]] = {}

    for unit in load_characters_json():
        base_id = str(unit.get("base_id", "")).strip()
        name = normalize_text(str(unit.get("name", "")))
        if not base_id or not name:
            continue

        name_by_base_id[base_id] = name

        slug = extract_slug_from_url(str(unit.get("url", "")))
        if slug:
            slug_to_base_id[slug] = base_id

        name_to_base_ids.setdefault(name.casefold(), []).append(base_id)

    return CharacterLookups(
        name_by_base_id=name_by_base_id,
        slug_to_base_id=slug_to_base_id,
        name_to_base_ids=name_to_base_ids,
    )


def parse_integer_cell(value: str) -> int:
    normalized = normalize_text(value).replace(",", "")
    if not normalized:
        return 0
    return int(normalized)


def resolve_base_id(row: ParsedTableRow, visible_name: str, lookups: CharacterLookups) -> tuple[str | None, str | None]:
    if row.base_id_hint:
        return row.base_id_hint, "tooltip"

    slug = extract_slug_from_url(row.href)
    if slug and slug in lookups.slug_to_base_id:
        return lookups.slug_to_base_id[slug], "unit-slug"

    matching_base_ids = lookups.name_to_base_ids.get(visible_name.casefold(), [])
    if len(matching_base_ids) == 1:
        return matching_base_ids[0], "name"
    if len(matching_base_ids) > 1:
        return None, f"ambiguous name match for {visible_name}: {matching_base_ids}"

    return None, f"no BaseID match for {visible_name}"


def parse_source_file(source: str, file_path: Path, lookups: CharacterLookups) -> tuple[list[dict[str, object]], list[str]]:
    warnings: list[str] = []
    html_text = file_path.read_text(encoding="utf-8")

    parser = RelicTableParser()
    parser.feed(html_text)

    if not parser.rows:
        return [], [f"[{source}] no relic rows found in HTML table"]

    records: list[dict[str, object]] = []
    seen_base_ids: set[str] = set()

    for parsed_row in parser.rows:
        if len(parsed_row.cells) < 12:
            warnings.append(f"[{source}] skipped malformed row with {len(parsed_row.cells)} cells")
            continue

        visible_name = normalize_text(parsed_row.cells[0])
        base_id, resolution_detail = resolve_base_id(parsed_row, visible_name, lookups)
        if not base_id:
            warnings.append(f"[{source}] unresolved row: {resolution_detail}")
            continue

        if base_id in seen_base_ids:
            warnings.append(f"[{source}] duplicate row ignored for {base_id}")
            continue

        seen_base_ids.add(base_id)
        canonical_name = lookups.name_by_base_id.get(base_id, visible_name)

        try:
            counts = {
                relic_column: parse_integer_cell(parsed_row.cells[index + 1])
                for index, relic_column in enumerate(RELIC_COLUMNS)
            }
        except ValueError as error:
            warnings.append(f"[{source}] invalid numeric row for {base_id}: {error}")
            continue

        record: dict[str, object] = {
            "source": source,
            "BaseID": base_id,
            "Name": canonical_name,
            "updated": normalize_text(parsed_row.cells[11]),
        }
        record.update(counts)
        records.append(record)

    if not records:
        warnings.append(f"[{source}] no valid relic rows could be parsed")

    return records, warnings


def load_existing_raw_catalog(csv_path: Path) -> dict[tuple[str, str], dict[str, object]]:
    if not csv_path.exists():
        return {}

    records: dict[tuple[str, str], dict[str, object]] = {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            source = normalize_text(row.get("source", ""))
            base_id = normalize_text(row.get("BaseID", ""))
            name = normalize_text(row.get("Name", ""))
            if not source or not base_id or not name:
                continue

            record: dict[str, object] = {
                "source": source,
                "BaseID": base_id,
                "Name": name,
                "updated": normalize_text(row.get("updated", "")),
            }
            for relic_column in RELIC_COLUMNS:
                record[relic_column] = parse_integer_cell(row.get(relic_column, "0"))
            records[(source, base_id)] = record

    return records


def load_existing_benchmark_catalog(csv_path: Path) -> dict[str, dict[str, object]]:
    if not csv_path.exists():
        return {}

    records: dict[str, dict[str, object]] = {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            base_id = normalize_text(row.get("BaseID", ""))
            name = normalize_text(row.get("Name", ""))
            if not base_id or not name:
                continue

            record: dict[str, object] = {
                "BaseID": base_id,
                "Name": name,
            }
            for benchmark_column in BENCHMARK_COLUMNS.values():
                raw_value = normalize_text(row.get(benchmark_column, ""))
                record[benchmark_column] = int(raw_value) if raw_value else None
            records[base_id] = record

    return records


def merge_raw_records(
    current_records: list[dict[str, object]],
    existing_records: dict[tuple[str, str], dict[str, object]],
) -> tuple[list[dict[str, object]], list[str]]:
    warnings: list[str] = []
    merged_records = dict(existing_records)
    current_keys = set()

    for record in current_records:
        key = (str(record["source"]), str(record["BaseID"]))
        current_keys.add(key)
        existing_record = merged_records.get(key)
        if existing_record and existing_record != record:
            warnings.append(f"[raw] updating existing record for {key[0]}:{key[1]}")
        merged_records[key] = record

    for key in sorted(existing_records):
        if key not in current_keys:
            warnings.append(f"[raw] preserving existing record not present in current parser run: {key[0]}:{key[1]}")

    sorted_records = sorted(
        merged_records.values(),
        key=lambda record: (str(record["source"]), str(record["Name"]).casefold(), str(record["BaseID"])),
    )
    return sorted_records, warnings


def merge_benchmark_records(
    current_records: list[dict[str, object]],
    existing_records: dict[str, dict[str, object]],
) -> tuple[list[dict[str, object]], list[str]]:
    warnings: list[str] = []
    merged_records = dict(existing_records)
    current_base_ids = set()

    for record in current_records:
        base_id = str(record["BaseID"])
        current_base_ids.add(base_id)
        existing_record = merged_records.get(base_id)
        if existing_record and existing_record != record:
            warnings.append(f"[benchmark] updating existing record for {base_id}")
        merged_records[base_id] = record

    for base_id in sorted(existing_records):
        if base_id not in current_base_ids:
            warnings.append(f"[benchmark] preserving existing record not present in current parser run: {base_id}")

    sorted_records = sorted(
        merged_records.values(),
        key=lambda record: (str(record["Name"]).casefold(), str(record["BaseID"])),
    )
    return sorted_records, warnings


def calculate_relic_benchmark(record: dict[str, object]) -> int | None:
    total_players = sum(int(record[relic_column]) for relic_column in RELIC_COLUMNS)
    if total_players <= 0:
        return None

    threshold = (total_players + 1) // 2
    cumulative = 0

    for relic_level in range(10, 0, -1):
        cumulative += int(record[f"r{relic_level}"])
        if cumulative >= threshold:
            return relic_level

    return 1


def build_benchmark_records(raw_records: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped_records: dict[str, dict[str, object]] = {}

    for raw_record in raw_records:
        source = str(raw_record["source"])
        base_id = str(raw_record["BaseID"])
        benchmark_column = BENCHMARK_COLUMNS.get(source)
        if not benchmark_column:
            continue

        benchmark_record = grouped_records.setdefault(
            base_id,
            {
                "BaseID": base_id,
                "Name": str(raw_record["Name"]),
                "unit_relic_all": None,
                "unit_relic_guilds_100": None,
                "unit_relic_kyber_1000": None,
            },
        )
        benchmark_record[benchmark_column] = calculate_relic_benchmark(raw_record)

    return sorted(
        grouped_records.values(),
        key=lambda record: (str(record["Name"]).casefold(), str(record["BaseID"])),
    )


def write_raw_catalog(records: list[dict[str, object]], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["source", "BaseID", "Name", *RELIC_COLUMNS, "updated"]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def write_benchmark_catalog(records: list[dict[str, object]], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["BaseID", "Name", *BENCHMARK_COLUMNS.values()]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def main() -> int:
    if not CHARACTERS_JSON_PATH.exists():
        raise FileNotFoundError(f"Character catalog file not found: {CHARACTERS_JSON_PATH}")

    lookups = build_character_lookups()
    parsed_raw_records: list[dict[str, object]] = []
    all_warnings: list[str] = []

    for source, file_path in SOURCE_FILES.items():
        if not file_path.exists():
            all_warnings.append(f"[{source}] source file not found: {file_path}")
            continue

        source_records, source_warnings = parse_source_file(source, file_path, lookups)
        parsed_raw_records.extend(source_records)
        all_warnings.extend(source_warnings)
        print(f"Parsed {source} from {file_path.name}: {len(source_records)} rows")

    if not parsed_raw_records:
        raise RuntimeError("No relic rows could be parsed from the configured source files")

    existing_raw_records = load_existing_raw_catalog(RAW_OUTPUT_CSV_PATH)
    merged_raw_records, raw_merge_warnings = merge_raw_records(parsed_raw_records, existing_raw_records)
    all_warnings.extend(raw_merge_warnings)
    write_raw_catalog(merged_raw_records, RAW_OUTPUT_CSV_PATH)

    current_benchmark_records = build_benchmark_records(merged_raw_records)
    existing_benchmark_records = load_existing_benchmark_catalog(BENCHMARK_OUTPUT_CSV_PATH)
    merged_benchmark_records, benchmark_merge_warnings = merge_benchmark_records(
        current_benchmark_records,
        existing_benchmark_records,
    )
    all_warnings.extend(benchmark_merge_warnings)
    write_benchmark_catalog(merged_benchmark_records, BENCHMARK_OUTPUT_CSV_PATH)

    print(
        f"Wrote {len(merged_raw_records)} raw rows to {RAW_OUTPUT_CSV_PATH} and "
        f"{len(merged_benchmark_records)} benchmark rows to {BENCHMARK_OUTPUT_CSV_PATH}"
    )

    if all_warnings:
        print("Warnings:")
        for warning in all_warnings:
            print(f"- {warning}")
    else:
        print("No warnings.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())