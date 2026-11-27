from pathlib import Path

import pyreadstat
import sys

from django.core.management.base import BaseCommand, CommandError

from pages.models import WavePageQuestion
from variables.models import Variable
from waves.models import Survey, Wave
from waves.choices import QuestionnairePart

from collections import Counter
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter


class Command(BaseCommand):
    help = "Abgleich der SLC-Variablen mit Stata-Metadaten"

    def add_arguments(self, parser):
        parser.add_argument(
            "stata_file",
            type=str,
            nargs="?",
        )

        parser.add_argument(
            "--wave-id",
            type=int,
        )

        parser.add_argument(
            "--part",
            choices=QuestionnairePart.values,
        )

    def handle(self, *args, **options):

        try:
            wave, part, stata_file = self.resolve_arguments(options)

        except (KeyboardInterrupt, EOFError):
            raise CommandError("Variablenabgleich abgebrochen.")

        wave_id = wave.pk

        self.stdout.write("")

        self.stdout.write(f"Befragungsgruppe: {wave}")
        self.stdout.write(f"Fragebogenteil: {part}")

        # Beide Variablenbestände auslesen
        stata_variables = self.load_stata_variables(stata_file)
        slc_variables = self.load_slc_variables(wave, part)

        # Technische Variablen auch auf Stata-Seite ausschließen
        technical_names = set(
            Variable.objects.filter(
                is_technical=True,
                varname__in=stata_variables.keys(),
            ).values_list("varname", flat=True)
        )

        for varname in technical_names:
            stata_variables.pop(varname, None)

        # Variablenbestände vergleichen
        variable_rows, value_rows = self.compare_variables(
            slc_variables,
            stata_variables,
        )

        # Zusammenfassung ausgeben
        self.stdout.write("")
        self.stdout.write(f"Variablen SLC: {len(slc_variables)}")
        self.stdout.write(f"Variablen Stata: {len(stata_variables)}")
        self.stdout.write(
            f"Technische Variablen ausgeschlossen: {len(technical_names)}"
        )

        self.stdout.write("\nErgebnis des Abgleichs:")
        self.stdout.write("-" * 50)

        for status in [
            "Identisch",
            "Abweichung",
            "Nur SLCDB",
            "Nur Stata",
        ]:
            count = sum(
                row["status"] == status
                for row in variable_rows
            )
            self.stdout.write(f"{status}: {count}")

        self.stdout.write("\nDetails der Abweichungen:")

        self.stdout.write(
            f"Variablenlabel: "
            f"{sum(row['varlab_diff'] for row in variable_rows)}"
        )

        self.stdout.write(
            f"Wertelabelcontainernamen: "
            f"{sum(row['vallabname_diff'] for row in variable_rows)}"
        )

        self.stdout.write(
            f"Variablen mit abweichenden Wertelabeln: "
            f"{sum(row['values_diff'] for row in variable_rows)}"
        )

        self.stdout.write(
            f"Abweichende einzelne Wertelabel: {len(value_rows)}"
        )

        # Dateinamen für den Prüfbericht erzeugen
        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        output_file = stata_file.with_name(
            f"Variablenabgleich_Wave{wave_id}_{part}_{timestamp}.xlsx"
        )

        # Vorhandene Prüfberichte nicht überschreiben
        if output_file.exists():
            raise CommandError(
                f"Die Ausgabedatei existiert bereits: {output_file}"
            )

        # Excel-Prüfbericht erstellen
        self.export_excel(
            variable_rows,
            value_rows,
            output_file,
        )

        self.stdout.write(
            self.style.SUCCESS(
                "\nVariablenabgleich abgeschlossen."
            )
        )

        self.stdout.write(
            f"Prüfbericht gespeichert unter:\n{output_file}"
        )

        self.stdout.write(
            "\nKeine Änderungen an der Datenbank vorgenommen."
        )

    def load_stata_variables(self, stata_file):

        if not stata_file.is_file():
            raise CommandError("Die Stata-Datei wurde nicht gefunden.")

        _, meta = pyreadstat.read_dta(
            str(stata_file),
            metadataonly=True,
            user_missing=True,
            output_format="dict",
        )

        # Ausschließlich Dateien ohne Beobachtungen zulassen
        if meta.number_rows != 0:
            raise CommandError(
                "Die Stata-Datei enthält Beobachtungen "
                "oder die Beobachtungszahl konnte nicht ermittelt werden."
            )

        return {
            varname: {
                "varlab": meta.column_names_to_labels.get(varname) or "",
                "vallabname": meta.variable_to_label.get(varname) or "",
                "values": meta.variable_value_labels.get(varname, {}),
            }
            for varname in meta.column_names
        }

    def load_slc_variables(self, wave, part):

        # Fragen der ausgewählten Gruppe und des Fragebogenteils
        question_ids = WavePageQuestion.objects.filter(
            wave_page__waves=wave,
            wave_page__questionnaire_part=part,
            waves=wave,
        ).values_list("question_id", flat=True)

        # Variablen dieser Fragen für die ausgewählte Gruppe
        variables = Variable.objects.filter(
            question_variable_wave_links__wave=wave,
            question_variable_wave_links__question_id__in=question_ids,
            is_technical=False,
        ).select_related("vallab").distinct().order_by("varname")

        return {
            variable.varname: {
                "varlab": variable.varlab or "",
                "vallabname": (
                    variable.vallab.vallabname
                    if variable.vallab else ""
                ),
                "values": (
                    variable.vallab.value_map()
                    if variable.vallab else {}
                ),
            }
            for variable in variables
        }

    def compare_variables(self, slc_variables, stata_variables):

        variable_rows = []
        value_rows = []

        # Alle Variablennamen aus beiden Beständen
        all_varnames = sorted(
            set(slc_variables) | set(stata_variables)
        )

        for varname in all_varnames:

            slc = slc_variables.get(varname)
            stata = stata_variables.get(varname)

            # Metadaten beider Quellen gegenüberstellen
            row = {
                "varname": varname,
                "varlab_slc": slc["varlab"] if slc else None,
                "varlab_stata": stata["varlab"] if stata else None,
                "vallabname_slc": slc["vallabname"] if slc else None,
                "vallabname_stata": stata["vallabname"] if stata else None,
                "varlab_diff": False,
                "vallabname_diff": False,
                "values_diff": False,
                "status": "",
            }

            # Variable nur in einem Bestand vorhanden
            if stata is None:
                row["status"] = "Nur SLCDBDB"

            elif slc is None:
                row["status"] = "Nur Stata"

            else:

                # Variablenlabel vergleichen
                row["varlab_diff"] = (
                    slc["varlab"] != stata["varlab"]
                )

                # Namen der Wertelabelcontainer vergleichen
                row["vallabname_diff"] = (
                    slc["vallabname"] != stata["vallabname"]
                )

                # Inhalte der Wertelabelcontainer vergleichen
                row["values_diff"] = (
                    slc["values"] != stata["values"]
                )

                if any([
                    row["varlab_diff"],
                    row["vallabname_diff"],
                    row["values_diff"],
                ]):
                    row["status"] = "Abweichung"
                else:
                    row["status"] = "Identisch"

                # Abweichende einzelne Wertelabel erfassen
                if row["values_diff"]:

                    all_values = sorted(
                        set(slc["values"]) | set(stata["values"]),
                        key=lambda value: (
                            isinstance(value, str), value
                        ),
                    )

                    for value in all_values:

                        label_slc = slc["values"].get(value)
                        label_stata = stata["values"].get(value)

                        if label_slc != label_stata:
                            value_rows.append({
                                "varname": varname,
                                "value": value,
                                "label_slc": label_slc,
                                "label_stata": label_stata,
                            })

            variable_rows.append(row)

        return variable_rows, value_rows 

    def export_excel(self, variable_rows, value_rows, output_file):

        workbook = Workbook()

        # Farben und Formatierungen
        header_fill = PatternFill(
            "solid", fgColor="334155"
        )
        header_font = Font(
            color="FFFFFF", bold=True
        )

        yellow_fill = PatternFill(
            "solid", fgColor="FFF0CC"
        )
        red_fill = PatternFill(
            "solid", fgColor="F8DCDC"
        )
        green_fill = PatternFill(
            "solid", fgColor="E4F1E7"
        )

        # Anzahl abweichender Wertelabel je Variable
        value_counts = Counter(
            row["varname"] for row in value_rows
        )

        # ------------------------------------------
        # Tabellenblatt 1: Variablenabgleich
        # ------------------------------------------

        ws = workbook.active
        ws.title = "Variablenabgleich"

        ws.append([
            "Variablenname",
            "Variablenlabel SLCDB",
            "Variablenlabel Stata",
            "Wertelabelcontainer SLCDB",
            "Wertelabelcontainer Stata",
            "Wertelabel",
            "Anzahl abweichender Wertelabel",
            "Status",
        ])

        for row in variable_rows:

            missing = row["status"] in [
                "Nur SLCDB", "Nur Stata"
            ]

            if missing:
                values_status = "Nicht vergleichbar"
            elif row["values_diff"]:
                values_status = "Abweichend"
            else:
                values_status = "Identisch"

            ws.append([
                row["varname"],
                row["varlab_slc"],
                row["varlab_stata"],
                row["vallabname_slc"],
                row["vallabname_stata"],
                values_status,
                None if missing else value_counts[row["varname"]],
                row["status"],
            ])

            r = ws.max_row

            # Abweichende Variablenlabel markieren
            if row["varlab_diff"]:
                ws.cell(r, 2).fill = yellow_fill
                ws.cell(r, 3).fill = yellow_fill

            # Abweichende Containernamen markieren
            if row["vallabname_diff"]:
                ws.cell(r, 4).fill = yellow_fill
                ws.cell(r, 5).fill = yellow_fill

            # Abweichende Wertelabel markieren
            if row["values_diff"]:
                ws.cell(r, 6).fill = yellow_fill
                ws.cell(r, 7).fill = yellow_fill

            # Status markieren
            if missing:
                ws.cell(r, 1).fill = red_fill
                ws.cell(r, 8).fill = red_fill

            elif row["status"] == "Abweichung":
                ws.cell(r, 8).fill = yellow_fill

            else:
                ws.cell(r, 8).fill = green_fill

        # Spaltenbreiten
        widths = [20, 55, 55, 28, 28, 22, 24, 20]

        for i, width in enumerate(widths, start=1):
            ws.column_dimensions[
                get_column_letter(i)
            ].width = width

        # ------------------------------------------
        # Tabellenblatt 2: Wertelabelabgleich
        # ------------------------------------------

        ws_values = workbook.create_sheet(
            "Wertelabelabgleich"
        )

        ws_values.append([
            "Variablenname",
            "Wert",
            "Wertelabel SLCDB",
            "Wertelabel Stata",
            "Status",
        ])

        for row in value_rows:

            if row["label_slc"] is None:
                status = "Nur Stata"

            elif row["label_stata"] is None:
                status = "Nur SLCDB"

            else:
                status = "Abweichung"

            ws_values.append([
                row["varname"],
                row["value"],
                row["label_slc"],
                row["label_stata"],
                status,
            ])

            r = ws_values.max_row

            ws_values.cell(r, 3).fill = yellow_fill
            ws_values.cell(r, 4).fill = yellow_fill

            ws_values.cell(r, 5).fill = (
                yellow_fill
                if status == "Abweichung"
                else red_fill
            )

        widths = [20, 12, 60, 60, 20]

        for i, width in enumerate(widths, start=1):
            ws_values.column_dimensions[
                get_column_letter(i)
            ].width = width

        # ------------------------------------------
        # Gemeinsame Formatierung
        # ------------------------------------------

        for sheet in workbook.worksheets:

            # Texte ausdrücklich als Texte speichern
            for cells in sheet.iter_rows():
                for cell in cells:
                    if isinstance(cell.value, str):
                        cell.data_type = "s"

                    cell.alignment = Alignment(
                        vertical="top",
                        wrap_text=True,
                    )

            # Kopfzeile formatieren
            for cell in sheet[1]:
                cell.fill = header_fill
                cell.font = header_font

            sheet.row_dimensions[1].height = 32

            # Kopfzeile und erste Spalte fixieren
            sheet.freeze_panes = "B2"

            # Autofilter aktivieren
            sheet.auto_filter.ref = sheet.dimensions

            # Gitternetzlinien ausblenden
            sheet.sheet_view.showGridLines = False

        # Excel-Datei speichern
        workbook.save(output_file)


    # Auswahl einer Option aus einer Liste von Wahlmöglichkeiten
    # für Aufruf ohne Parameter
    def select_option(self, title, choices):

        if not choices:
            raise CommandError(
                "Es stehen keine Auswahlmöglichkeiten zur Verfügung."
            )

        self.stdout.write(f"\n{title}\n")

        for i, (value, label) in enumerate(choices, start=1):
            self.stdout.write(f"  {i}. {label}")

        while True:

            selection = input("\nAuswahl: ").strip()

            try:
                index = int(selection) - 1

                if 0 <= index < len(choices):
                    return choices[index][0]

            except ValueError:
                pass

            self.stdout.write(
                self.style.WARNING(
                    "Ungültige Auswahl. Bitte erneut versuchen."
                )
            )

    # Parameter auflösen und ggf. interaktiv abfragen
    def resolve_arguments(self, options):

        wave_id = options["wave_id"]
        part = options["part"]
        stata_file = options["stata_file"]

        # Fehlende Parameter nur in interaktiver Shell abfragen
        if (
            wave_id is None
            or part is None
            or not stata_file
        ) and not sys.stdin.isatty():
            raise CommandError(
                "Bitte alle Parameter angeben oder "
                "den Befehl interaktiv ausführen."
            )

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "\nSLCDB – Variablenabgleich"
            )
        )

        # ------------------------------------------
        # Befragung und Gruppe auswählen
        # ------------------------------------------

        if wave_id is None:

            surveys = Survey.objects.filter(
                waves__isnull=False
            ).distinct().order_by("-year", "name")

            survey_id = self.select_option(
                "Befragung auswählen:",
                [
                    (survey.pk, survey.name)
                    for survey in surveys
                ],
            )

            waves = Wave.objects.filter(
                survey_id=survey_id
            ).order_by("cycle", "instrument")

            wave_id = self.select_option(
                "Befragungsgruppe auswählen:",
                [
                    (
                        wave.pk,
                        f"{wave.cycle} – {wave.instrument}",
                    )
                    for wave in waves
                ],
            )

        # Befragungsgruppe ermitteln
        try:
            wave = Wave.objects.select_related(
                "survey"
            ).get(pk=wave_id)

        except Wave.DoesNotExist:
            raise CommandError(
                "Die Befragungsgruppe existiert nicht."
            )

        # ------------------------------------------
        # Fragebogenteil auswählen
        # ------------------------------------------

        available_parts = set(
            wave.pages.values_list(
                "questionnaire_part",
                flat=True,
            )
        )

        if part is None:

            part = self.select_option(
                "Fragebogenteil auswählen:",
                [
                    (value, label)
                    for value, label in QuestionnairePart.choices
                    if value in available_parts
                ],
            )

        if part not in available_parts:
            raise CommandError(
                "Für den ausgewählten Fragebogenteil "
                "sind keine Seiten vorhanden."
            )

        # ------------------------------------------
        # Stata-Datei auswählen
        # ------------------------------------------

        if not stata_file:

            while True:

                stata_file = input(
                    "\nPfad zur Stata-Metadatendatei: "
                ).strip().strip('"')

                if stata_file and Path(stata_file).expanduser().is_file():
                    break

                self.stdout.write(
                    self.style.WARNING(
                        "Datei nicht gefunden. "
                        "Bitte erneut versuchen."
                    )
                )

        return wave, part, Path(stata_file).expanduser()