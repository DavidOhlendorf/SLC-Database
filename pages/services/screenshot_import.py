# pages/services/screenshot_import.py
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings
from django.db import transaction

from pages.models import WavePage, WavePageScreenshot


REQUIRED_COLUMNS = {"pagename", "screenshotname", "language", "device"}


@dataclass
class ImportRowResult:
    row_number: int
    pagename: str
    screenshotname: str
    language: str
    device: str
    status: str
    message: str = ""
    matched_page_ids: list[int] = field(default_factory=list)


@dataclass
class ImportSummary:
    total_rows: int = 0
    imported: int = 0
    skipped_existing: int = 0
    missing_page: int = 0
    missing_file: int = 0
    ambiguous_page: int = 0
    invalid_rows: int = 0
    results: list[ImportRowResult] = field(default_factory=list)


def _read_csv(uploaded_file) -> list[dict]:
    raw = uploaded_file.read()

    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("CSV-Datei konnte nicht dekodiert werden.")

    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    if reader.fieldnames is None:
        raise ValueError("CSV-Datei enthält keine Kopfzeile.")

    normalized_fields = {f.strip() for f in reader.fieldnames if f}
    missing = REQUIRED_COLUMNS - normalized_fields
    if missing:
        raise ValueError(
            f"Fehlende Pflichtspalten: {', '.join(sorted(missing))}"
        )

    rows = []
    for row in reader:
        normalized = {str(k).strip(): (str(v).strip() if v is not None else "") for k, v in row.items()}
        rows.append(normalized)

    return rows


def import_screenshots_from_csv(
    *,
    uploaded_file,
    screenshot_dir: str,
    wave_ids: list[int],
    execute_import: bool,
) -> ImportSummary:
    """
    screenshot_dir ist relativ zu MEDIA_ROOT, z.B. 'screenshots/EJ2024/AB'
    """
    rows = _read_csv(uploaded_file)
    summary = ImportSummary(total_rows=len(rows))

    media_root = Path(settings.MEDIA_ROOT)
    base_dir = media_root / screenshot_dir

    # Alle relevanten Seiten aus den ausgewählten Waves
    candidate_pages = (
        WavePage.objects
        .filter(wave_links__wave_id__in=wave_ids)
        .distinct()
    )

    pages_by_name: dict[str, list[WavePage]] = {}
    for page in candidate_pages:
        pages_by_name.setdefault(page.pagename.strip(), []).append(page)

    actions: list[tuple[WavePage, str, str, str]] = []

    for idx, row in enumerate(rows, start=2):  # Kopfzeile ist Zeile 1
        pagename = row.get("pagename", "").strip()
        screenshotname = row.get("screenshotname", "").strip()
        language = row.get("language", "").strip().lower()
        device = row.get("device", "").strip().lower()

        if not pagename or not screenshotname or not language or not device:
            summary.invalid_rows += 1
            summary.results.append(
                ImportRowResult(
                    row_number=idx,
                    pagename=pagename,
                    screenshotname=screenshotname,
                    language=language,
                    device=device,
                    status="invalid",
                    message="Mindestens eines der Pflichtfelder ist leer.",
                )
            )
            continue

        file_path = base_dir / screenshotname
        if not file_path.exists():
            summary.missing_file += 1
            summary.results.append(
                ImportRowResult(
                    row_number=idx,
                    pagename=pagename,
                    screenshotname=screenshotname,
                    language=language,
                    device=device,
                    status="missing_file",
                    message=f"Datei nicht gefunden: {file_path}",
                )
            )
            continue

        matched_pages = pages_by_name.get(pagename, [])

        if not matched_pages:
            summary.missing_page += 1
            summary.results.append(
                ImportRowResult(
                    row_number=idx,
                    pagename=pagename,
                    screenshotname=screenshotname,
                    language=language,
                    device=device,
                    status="missing_page",
                    message="Keine passende Seite in den ausgewählten Waves gefunden.",
                )
            )
            continue

        if len(matched_pages) > 1:
            summary.ambiguous_page += 1
            summary.results.append(
                ImportRowResult(
                    row_number=idx,
                    pagename=pagename,
                    screenshotname=screenshotname,
                    language=language,
                    device=device,
                    status="ambiguous_page",
                    message="Mehrere passende Seiten gefunden. Import für diese Zeile abgebrochen.",
                    matched_page_ids=[p.id for p in matched_pages],
                )
            )
            continue

        page = matched_pages[0]

        already_exists = WavePageScreenshot.objects.filter(
            wave_page=page,
            language=language,
            device=device,
        ).exists()

        if already_exists:
            summary.skipped_existing += 1
            summary.results.append(
                ImportRowResult(
                    row_number=idx,
                    pagename=pagename,
                    screenshotname=screenshotname,
                    language=language,
                    device=device,
                    status="existing",
                    message="Für Seite/Sprache/Device existiert bereits ein Screenshot.",
                    matched_page_ids=[page.id],
                )
            )
            continue

        relative_image_path = str(Path("media") / screenshot_dir / screenshotname).replace("\\", "/")

        actions.append((page, relative_image_path, language, device))
        summary.results.append(
            ImportRowResult(
                row_number=idx,
                pagename=pagename,
                screenshotname=screenshotname,
                language=language,
                device=device,
                status="ready" if not execute_import else "imported",
                message="Importierbar." if not execute_import else "Importiert.",
                matched_page_ids=[page.id],
            )
        )

    if execute_import and actions:
        with transaction.atomic():
            WavePageScreenshot.objects.bulk_create(
                [
                    WavePageScreenshot(
                        wave_page=page,
                        image_path=image_path,
                        language=language,
                        device=device,
                    )
                    for page, image_path, language, device in actions
                ]
            )

        summary.imported = len(actions)

    return summary