from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
ERA_HTML_DIR = ROOT_DIR / "data" / "swgoh_gg" / "Eras"
CONQUEST_HTML_DIR = ROOT_DIR / "data" / "swgoh_gg" / "Conquest"
CHARACTERS_JSON_PATH = ROOT_DIR / "data" / "swgoh_gg" / "characters.json"
SHIPS_JSON_PATH = ROOT_DIR / "data" / "ships.json"
OUTPUT_CSV_PATH = ROOT_DIR / "data" / "unit_era_catalog.csv"
CONQUEST_ERA_NAME = "Conquest"

UNITS_HEADER_MARKER = '<h3 class="text-lg font-bold mb-0">Units'
LOANED_UNITS_HEADER_MARKER = '<h3 class="text-lg font-bold mb-0">Loaned Units'

ERA_LINK_BASE_ID_PATTERN = re.compile(r"/eras/[^/]+/unit/([A-Z0-9_]+)/")
UNIT_SLUG_PATTERN = re.compile(r"/units/([^/]+)/")
IMAGE_URL_PATTERN = re.compile(r"url\(([^)]+)\)")


@dataclass(frozen=True)
class ParsedUnitCard:
    href: str
    name: str
    image_url: str | None


@dataclass
class CatalogLookups:
    unit_by_base_id: dict[str, dict[str, str]]
    slug_to_base_id: dict[str, str]
    image_to_base_ids: dict[str, list[str]]
    name_to_base_ids: dict[str, list[str]]


class EraUnitsSectionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.cards: list[ParsedUnitCard] = []
        self.current_href: str | None = None
        self.current_image_url: str | None = None
        self.current_name_parts: list[str] = []
        self.capture_name = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        class_value = attrs_dict.get("class", "") or ""

        if tag == "a":
            href = attrs_dict.get("href")
            if href and ("/unit/" in href or "/units/" in href):
                self.current_href = href
                self.current_image_url = None
                self.current_name_parts = []
                self.capture_name = False
            return

        if not self.current_href:
            return

        if "unit-card__name" in class_value:
            self.capture_name = True

        style_value = attrs_dict.get("style")
        if style_value and "character-portrait--image-url" in style_value:
            image_match = IMAGE_URL_PATTERN.search(style_value)
            if image_match:
                self.current_image_url = image_match.group(1).strip().strip('"\'')

    def handle_endtag(self, tag: str) -> None:
        if tag == "div" and self.capture_name:
            self.capture_name = False
            return

        if tag == "a" and self.current_href:
            name = normalize_unit_name(" ".join(self.current_name_parts))
            if name:
                self.cards.append(
                    ParsedUnitCard(
                        href=self.current_href,
                        name=name,
                        image_url=self.current_image_url,
                    )
                )
            self.current_href = None
            self.current_image_url = None
            self.current_name_parts = []
            self.capture_name = False

    def handle_data(self, data: str) -> None:
        if self.capture_name and self.current_href:
            cleaned_text = normalize_unit_name(data)
            if cleaned_text:
                self.current_name_parts.append(cleaned_text)


class ConquestUnitsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.cards: list[ParsedUnitCard] = []
        self.current_href: str | None = None
        self.current_image_url: str | None = None
        self.current_name_parts: list[str] = []
        self.capture_name = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        class_value = attrs_dict.get("class", "") or ""

        if tag == "a":
            href = attrs_dict.get("href")
            if href and "/conquest/" in href and "conquest-card" in class_value:
                self.current_href = href
                self.current_image_url = None
                self.current_name_parts = []
                self.capture_name = False
            return

        if not self.current_href:
            return

        if "conquest-card__unit" in class_value:
            self.capture_name = True

        style_value = attrs_dict.get("style")
        if style_value and "character-portrait--image-url" in style_value:
            image_match = IMAGE_URL_PATTERN.search(style_value)
            if image_match:
                self.current_image_url = image_match.group(1).strip().strip('"\'')

    def handle_endtag(self, tag: str) -> None:
        if tag == "div" and self.capture_name:
            self.capture_name = False
            return

        if tag == "a" and self.current_href:
            name = normalize_unit_name(" ".join(self.current_name_parts))
            if name:
                self.cards.append(
                    ParsedUnitCard(
                        href=self.current_href,
                        name=name,
                        image_url=self.current_image_url,
                    )
                )
            self.current_href = None
            self.current_image_url = None
            self.current_name_parts = []
            self.capture_name = False

    def handle_data(self, data: str) -> None:
        if self.capture_name and self.current_href:
            cleaned_text = normalize_unit_name(data)
            if cleaned_text:
                self.current_name_parts.append(cleaned_text)


def normalize_unit_name(value: str) -> str:
    return " ".join(value.split())


def normalize_era_name(file_name: str) -> str:
    era_name = file_name.replace(" - SWGOH.GG.html", "").strip()
    if era_name.startswith("Era of "):
        era_name = era_name[len("Era of "):]
    if era_name.endswith(" Era"):
        era_name = era_name[: -len(" Era")]
    return normalize_unit_name(era_name)


def extract_relevant_units_section(html_text: str) -> str:
    start_index = html_text.find(UNITS_HEADER_MARKER)
    if start_index == -1:
        raise ValueError("Units section marker not found")

    end_index = html_text.find(LOANED_UNITS_HEADER_MARKER, start_index)
    if end_index == -1:
        return html_text[start_index:]

    return html_text[start_index:end_index]


def extract_slug_from_url(url: str | None) -> str | None:
    if not url:
        return None
    slug_match = UNIT_SLUG_PATTERN.search(url)
    if not slug_match:
        return None
    return slug_match.group(1).strip().casefold()


def extract_image_file_name(image_url: str | None) -> str | None:
    if not image_url:
        return None
    image_name = image_url.rsplit("/", 1)[-1].strip()
    return image_name.casefold() if image_name else None


def load_units_from_json(json_path: Path) -> list[dict[str, object]]:
    with json_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_catalog_lookups() -> CatalogLookups:
    unit_by_base_id: dict[str, dict[str, str]] = {}
    slug_to_base_id: dict[str, str] = {}
    image_to_base_ids: dict[str, list[str]] = {}
    name_to_base_ids: dict[str, list[str]] = {}

    for json_path in (CHARACTERS_JSON_PATH, SHIPS_JSON_PATH):
        if not json_path.exists():
            raise FileNotFoundError(f"Required catalog file not found: {json_path}")

        for unit in load_units_from_json(json_path):
            base_id = str(unit.get("base_id", "")).strip()
            name = normalize_unit_name(str(unit.get("name", "")))
            if not base_id or not name:
                continue

            unit_by_base_id[base_id] = {
                "BaseID": base_id,
                "Name": name,
            }

            slug = extract_slug_from_url(str(unit.get("url", "")))
            if slug:
                slug_to_base_id[slug] = base_id

            image_name = extract_image_file_name(str(unit.get("image", "")))
            if image_name:
                image_to_base_ids.setdefault(image_name, []).append(base_id)

            normalized_name = name.casefold()
            name_to_base_ids.setdefault(normalized_name, []).append(base_id)

    return CatalogLookups(
        unit_by_base_id=unit_by_base_id,
        slug_to_base_id=slug_to_base_id,
        image_to_base_ids=image_to_base_ids,
        name_to_base_ids=name_to_base_ids,
    )


def resolve_base_id(card: ParsedUnitCard, lookups: CatalogLookups) -> tuple[str | None, str]:
    direct_match = ERA_LINK_BASE_ID_PATTERN.search(card.href)
    if direct_match:
        return direct_match.group(1), "era-link"

    slug = extract_slug_from_url(card.href)
    if slug and slug in lookups.slug_to_base_id:
        return lookups.slug_to_base_id[slug], "unit-slug"

    image_name = extract_image_file_name(card.image_url)
    if image_name:
        matching_base_ids = lookups.image_to_base_ids.get(image_name, [])
        if len(matching_base_ids) == 1:
            return matching_base_ids[0], "image"
        if len(matching_base_ids) > 1:
            return None, f"ambiguous image match for {card.name}: {matching_base_ids}"

    matching_base_ids = lookups.name_to_base_ids.get(card.name.casefold(), [])
    if len(matching_base_ids) == 1:
        return matching_base_ids[0], "name"
    if len(matching_base_ids) > 1:
        return None, f"ambiguous name match for {card.name}: {matching_base_ids}"

    return None, f"no BaseID match for href={card.href!r}, name={card.name!r}"


def parse_era_file(file_path: Path, lookups: CatalogLookups) -> tuple[list[dict[str, str]], list[str]]:
    warnings: list[str] = []
    html_text = file_path.read_text(encoding="utf-8")
    era_name = normalize_era_name(file_path.name)

    try:
        relevant_section = extract_relevant_units_section(html_text)
    except ValueError as error:
        return [], [f"[{file_path.name}] {error}"]

    parser = EraUnitsSectionParser()
    parser.feed(relevant_section)

    if not parser.cards:
        warnings.append(f"[{file_path.name}] no unit cards found in relevant Units section")
        return [], warnings

    records: list[dict[str, str]] = []
    seen_base_ids: set[str] = set()

    for card in parser.cards:
        base_id, resolution_detail = resolve_base_id(card, lookups)
        if not base_id:
            warnings.append(f"[{file_path.name}] unresolved unit: {resolution_detail}")
            continue

        if base_id in seen_base_ids:
            warnings.append(f"[{file_path.name}] duplicate unit ignored: {base_id} ({card.name})")
            continue

        seen_base_ids.add(base_id)
        canonical_name = lookups.unit_by_base_id.get(base_id, {}).get("Name", card.name)
        records.append(
            {
                "BaseID": base_id,
                "Name": canonical_name,
                "era": era_name,
            }
        )

    if not records:
        warnings.append(f"[{file_path.name}] no units could be resolved")

    return records, warnings


def parse_conquest_file(file_path: Path, lookups: CatalogLookups) -> tuple[list[dict[str, str]], list[str]]:
    warnings: list[str] = []
    html_text = file_path.read_text(encoding="utf-8")

    parser = ConquestUnitsParser()
    parser.feed(html_text)

    if not parser.cards:
        warnings.append(f"[{file_path.name}] no conquest unit cards found")
        return [], warnings

    records: list[dict[str, str]] = []
    seen_base_ids: set[str] = set()

    for card in parser.cards:
        base_id, resolution_detail = resolve_base_id(card, lookups)
        if not base_id:
            warnings.append(f"[{file_path.name}] unresolved conquest unit: {resolution_detail}")
            continue

        if base_id in seen_base_ids:
            warnings.append(f"[{file_path.name}] duplicate conquest unit ignored: {base_id} ({card.name})")
            continue

        seen_base_ids.add(base_id)
        canonical_name = lookups.unit_by_base_id.get(base_id, {}).get("Name", card.name)
        records.append(
            {
                "BaseID": base_id,
                "Name": canonical_name,
                "era": CONQUEST_ERA_NAME,
            }
        )

    if not records:
        warnings.append(f"[{file_path.name}] no conquest units could be resolved")

    return records, warnings


def apply_conquest_overrides(
    parsed_records: list[dict[str, str]],
    conquest_records: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[str]]:
    records_by_base_id = {record["BaseID"]: dict(record) for record in parsed_records}

    for record in conquest_records:
        records_by_base_id[record["BaseID"]] = dict(record)

    return list(records_by_base_id.values()), []


def load_existing_catalog(csv_path: Path) -> dict[str, dict[str, str]]:
    if not csv_path.exists():
        return {}

    existing_records: dict[str, dict[str, str]] = {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            base_id = normalize_unit_name(row.get("BaseID", ""))
            name = normalize_unit_name(row.get("Name", ""))
            era = normalize_unit_name(row.get("era", ""))
            if not base_id or not name or not era:
                continue
            existing_records[base_id] = {
                "BaseID": base_id,
                "Name": name,
                "era": era,
            }

    return existing_records


def merge_with_existing_catalog(
    parsed_records: list[dict[str, str]],
    existing_records: dict[str, dict[str, str]],
) -> tuple[list[dict[str, str]], list[str]]:
    warnings: list[str] = []
    merged_records = dict(existing_records)
    parsed_base_ids = {record["BaseID"] for record in parsed_records}

    for record in parsed_records:
        existing_record = merged_records.get(record["BaseID"])
        if existing_record and existing_record.get("era") == CONQUEST_ERA_NAME and record.get("era") != CONQUEST_ERA_NAME:
            warnings.append(
                "[merge] preserving existing Conquest override for "
                f"{record['BaseID']}"
            )
            continue
        if existing_record and existing_record != record:
            warnings.append(
                "[merge] updating existing era record for "
                f"{record['BaseID']}: {existing_record['era']} -> {record['era']}"
            )
        merged_records[record["BaseID"]] = record

    preserved_base_ids = sorted(base_id for base_id in existing_records if base_id not in parsed_base_ids)
    for base_id in preserved_base_ids:
        warnings.append(
            f"[merge] preserving existing record not present in current parser run: {base_id}"
        )

    sorted_records = sorted(
        merged_records.values(),
        key=lambda record: (record["era"].casefold(), record["Name"].casefold(), record["BaseID"]),
    )
    return sorted_records, warnings


def write_catalog(records: list[dict[str, str]], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["BaseID", "Name", "era"])
        writer.writeheader()
        writer.writerows(records)


def main() -> int:
    if not ERA_HTML_DIR.exists():
        raise FileNotFoundError(f"Era HTML directory not found: {ERA_HTML_DIR}")

    lookups = build_catalog_lookups()
    html_files = sorted(ERA_HTML_DIR.glob("*.html"))
    if not html_files:
        raise FileNotFoundError(f"No Era HTML files found in {ERA_HTML_DIR}")

    all_records: list[dict[str, str]] = []
    all_warnings: list[str] = []

    for html_file in html_files:
        records, warnings = parse_era_file(html_file, lookups)
        all_records.extend(records)
        all_warnings.extend(warnings)
        print(f"Parsed {html_file.name}: {len(records)} units")

    if not all_records:
        raise RuntimeError("No era records were parsed from the current HTML files")

    conquest_records: list[dict[str, str]] = []
    if CONQUEST_HTML_DIR.exists():
        conquest_html_files = sorted(CONQUEST_HTML_DIR.glob("*.html"))
        if conquest_html_files:
            for html_file in conquest_html_files:
                records, warnings = parse_conquest_file(html_file, lookups)
                conquest_records.extend(records)
                all_warnings.extend(warnings)
                print(f"Parsed {html_file.name}: {len(records)} conquest units")
        else:
            all_warnings.append(f"[conquest] no Conquest HTML files found in {CONQUEST_HTML_DIR}")
    else:
        all_warnings.append(f"[conquest] Conquest HTML directory not found: {CONQUEST_HTML_DIR}")

    all_records, conquest_warnings = apply_conquest_overrides(all_records, conquest_records)
    all_warnings.extend(conquest_warnings)

    existing_records = load_existing_catalog(OUTPUT_CSV_PATH)
    merged_records, merge_warnings = merge_with_existing_catalog(all_records, existing_records)
    all_warnings.extend(merge_warnings)

    write_catalog(merged_records, OUTPUT_CSV_PATH)

    unique_base_ids = len({record["BaseID"] for record in merged_records})
    print(f"Wrote {len(merged_records)} rows for {unique_base_ids} unique units to {OUTPUT_CSV_PATH}")

    if all_warnings:
        print("Warnings:")
        for warning in all_warnings:
            print(f"- {warning}")
    else:
        print("No warnings.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())