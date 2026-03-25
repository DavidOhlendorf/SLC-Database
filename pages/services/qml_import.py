from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET

from django.db import transaction

from pages.models import WavePage, WavePageQml


@dataclass
class QmlImportRowResult:
    filename: str
    pagename_from_filename: str
    xml_uid: str
    status: str
    message: str = ""
    matched_page_ids: list[int] = field(default_factory=list)


@dataclass
class QmlImportSummary:
    total_files: int = 0
    imported: int = 0
    replaced: int = 0
    skipped_existing: int = 0
    missing_page: int = 0
    ambiguous_page: int = 0
    invalid_xml: int = 0
    invalid_zip_entries: int = 0
    uid_mismatch: int = 0
    duplicate_pagename_in_zip: int = 0
    results: list[QmlImportRowResult] = field(default_factory=list)


def _extract_xml_uid(xml_text: str) -> str:
    """
    Liest die UID des Root-Elements aus, z. B. <zofar:page uid="dem_08">.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f"XML ist nicht wohlgeformt: {exc}") from exc

    uid = (root.attrib.get("uid") or "").strip()
    return uid


def import_qml_from_zip(
    *,
    uploaded_file,
    survey_id: int,
    wave_ids: list[int],
    execute_import: bool,
    replace_existing: bool = False,
) -> QmlImportSummary:
    summary = QmlImportSummary()

    # Relevante Seiten bestimmen
    candidate_pages = WavePage.objects.filter(waves__survey_id=survey_id).distinct()

    if wave_ids:
        candidate_pages = candidate_pages.filter(wave_links__wave_id__in=wave_ids).distinct()

    pages_by_name: dict[str, list[WavePage]] = {}
    for page in candidate_pages:
        key = (page.pagename or "").strip()
        if key:
            pages_by_name.setdefault(key, []).append(page)

    actions: list[dict] = []
    seen_pagenames_in_zip: set[str] = set()

    try:
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            try:
                with ZipFile(uploaded_file) as zip_file:
                    zip_file.extractall(tmp_path)
            except BadZipFile as exc:
                raise ValueError("Die hochgeladene Datei ist keine gültige ZIP-Datei.") from exc

            xml_files = sorted(
                [
                    p for p in tmp_path.rglob("*")
                    if p.is_file() and p.suffix.lower() == ".xml"
                ]
            )

            summary.total_files = len(xml_files)

            if not xml_files:
                raise ValueError("Die ZIP-Datei enthält keine XML-Dateien.")

            for xml_file in xml_files:
                filename = xml_file.name
                pagename_from_filename = xml_file.stem.strip()

                if not pagename_from_filename:
                    summary.invalid_zip_entries += 1
                    summary.results.append(
                        QmlImportRowResult(
                            filename=filename,
                            pagename_from_filename="",
                            xml_uid="",
                            status="invalid_entry",
                            message="Dateiname ohne verwertbaren Seitennamen.",
                        )
                    )
                    continue

                if pagename_from_filename in seen_pagenames_in_zip:
                    summary.duplicate_pagename_in_zip += 1
                    summary.results.append(
                        QmlImportRowResult(
                            filename=filename,
                            pagename_from_filename=pagename_from_filename,
                            xml_uid="",
                            status="duplicate_in_zip",
                            message="Mehrere XML-Dateien mit demselben Seitennamen in der ZIP.",
                        )
                    )
                    continue
                seen_pagenames_in_zip.add(pagename_from_filename)

                try:
                    xml_text = xml_file.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    try:
                        xml_text = xml_file.read_text(encoding="utf-8-sig")
                    except UnicodeDecodeError:
                        summary.invalid_xml += 1
                        summary.results.append(
                            QmlImportRowResult(
                                filename=filename,
                                pagename_from_filename=pagename_from_filename,
                                xml_uid="",
                                status="invalid_xml",
                                message="XML-Datei konnte nicht als UTF-8 gelesen werden.",
                            )
                        )
                        continue

                try:
                    xml_uid = _extract_xml_uid(xml_text)
                except ValueError as exc:
                    summary.invalid_xml += 1
                    summary.results.append(
                        QmlImportRowResult(
                            filename=filename,
                            pagename_from_filename=pagename_from_filename,
                            xml_uid="",
                            status="invalid_xml",
                            message=str(exc),
                        )
                    )
                    continue

                if xml_uid and xml_uid != pagename_from_filename:
                    summary.uid_mismatch += 1
                    summary.results.append(
                        QmlImportRowResult(
                            filename=filename,
                            pagename_from_filename=pagename_from_filename,
                            xml_uid=xml_uid,
                            status="uid_mismatch",
                            message="Dateiname und XML-UID stimmen nicht überein.",
                        )
                    )
                    continue

                matched_pages = pages_by_name.get(pagename_from_filename, [])

                if not matched_pages:
                    summary.missing_page += 1
                    summary.results.append(
                        QmlImportRowResult(
                            filename=filename,
                            pagename_from_filename=pagename_from_filename,
                            xml_uid=xml_uid,
                            status="missing_page",
                            message="Keine passende Seite im gewählten Survey / den gewählten Waves gefunden.",
                        )
                    )
                    continue

                if len(matched_pages) > 1:
                    summary.ambiguous_page += 1
                    summary.results.append(
                        QmlImportRowResult(
                            filename=filename,
                            pagename_from_filename=pagename_from_filename,
                            xml_uid=xml_uid,
                            status="ambiguous_page",
                            message="Mehrere passende Seiten gefunden.",
                            matched_page_ids=[p.id for p in matched_pages],
                        )
                    )
                    continue

                page = matched_pages[0]
                try:
                    existing_qml = page.qml_file
                except WavePageQml.DoesNotExist:
                    existing_qml = None

                already_exists = existing_qml is not None

                if already_exists and not replace_existing:
                    summary.skipped_existing += 1
                    summary.results.append(
                        QmlImportRowResult(
                            filename=filename,
                            pagename_from_filename=pagename_from_filename,
                            xml_uid=xml_uid,
                            status="existing",
                            message="Für diese Seite existiert bereits eine QML-Datei.",
                            matched_page_ids=[page.id],
                        )
                    )
                    continue

                will_replace = already_exists and replace_existing

                actions.append(
                    {
                        "page": page,
                        "filename": filename,
                        "xml_uid": xml_uid,
                        "xml_text": xml_text,
                        "replace": will_replace,
                    }
                )

                if will_replace:
                    status = "replaced" if execute_import else "replace"
                    message = (
                        "Vorhandene QML-Datei wurde ersetzt."
                        if execute_import
                        else "Vorhandene QML-Datei wird ersetzt."
                    )
                else:
                    status = "imported" if execute_import else "ready"
                    message = "Importiert." if execute_import else "Importierbar."

                summary.results.append(
                    QmlImportRowResult(
                        filename=filename,
                        pagename_from_filename=pagename_from_filename,
                        xml_uid=xml_uid,
                        status=status,
                        message=message,
                        matched_page_ids=[page.id],
                    )
                )

            if execute_import and actions:
                with transaction.atomic():
                    for action in actions:
                        page = action["page"]

                        if action["replace"]:
                            WavePageQml.objects.update_or_create(
                                wave_page=page,
                                defaults={
                                    "source_filename": action["filename"],
                                    "xml_uid": action["xml_uid"],
                                    "xml_content": action["xml_text"],
                                },
                            )
                            summary.replaced += 1
                        else:
                            WavePageQml.objects.create(
                                wave_page=page,
                                source_filename=action["filename"],
                                xml_uid=action["xml_uid"],
                                xml_content=action["xml_text"],
                            )
                            summary.imported += 1

    except OSError as exc:
        raise ValueError(f"ZIP-Datei konnte nicht verarbeitet werden: {exc}") from exc

    return summary