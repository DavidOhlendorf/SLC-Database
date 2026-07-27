"""Hilfsfunktionen für die Versionierung von Variablennamen."""

from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Iterable

from django.db.models import Q

from .models import Variable


VARIABLE_NAME_RE = re.compile(
    r"^(?:(?P<prefix>[a-z]{2})_)?"
    r"(?P<stem>[a-z]{3}\d{3})"
    r"(?:_(?P<suffixes>(?:[vgpf]\d{1,2})+))?$",
    re.IGNORECASE,
)
SUFFIX_TOKEN_RE = re.compile(r"([vgpf])(\d{1,2})", re.IGNORECASE)
SUFFIX_ORDER = ("v", "g", "p", "f")
SUFFIX_RANK = {suffix: index for index, suffix in enumerate(SUFFIX_ORDER)}


class VariableNameSchemaError(ValueError):
    """Der Variablenname entspricht nicht dem SLC-Schema."""


@dataclass(frozen=True)
class ParsedVariableName:
    prefix: str | None
    stem: str
    suffixes: dict[str, int]

    @property
    def family_key(self) -> str:
        """Präfix und Stamm identifizieren die Variablenfamilie eindeutig."""
        return f"{self.prefix}_{self.stem}" if self.prefix else self.stem

    @property
    def version_number(self) -> int:
        """Nicht versionierte Variablen werden als Version 0 behandelt."""
        return self.suffixes.get("v", 0)

    @property
    def non_version_suffixes(self) -> dict[str, int]:
        """Liefert ausschließlich die fachlichen Suffixe g, p und f."""
        return {
            suffix: self.suffixes[suffix]
            for suffix in ("g", "p", "f")
            if suffix in self.suffixes
        }


    def with_version(self, version_number: int) -> "ParsedVariableName":
        if not 1 <= version_number <= 99:
            raise VariableNameSchemaError(
                "Die Versionsnummer muss zwischen 1 und 99 liegen."
            )
        suffixes = dict(self.suffixes)
        suffixes["v"] = version_number
        return replace(self, suffixes=suffixes)

    def format(self) -> str:
        suffix_text = "".join(
            f"{suffix}{self.suffixes[suffix]}"
            for suffix in SUFFIX_ORDER
            if suffix in self.suffixes
        )
        return (
            f"{self.family_key}_{suffix_text}"
            if suffix_text
            else self.family_key
        )


def parse_variable_name(varname: str) -> ParsedVariableName:
    """
    Zerlegt einen Variablennamen nach dem SLC-Schema.

    Beispiele:
    - dem123
    - dem123_v2g4p1
    - sf_dem123_v2f12
    """
    normalized = (varname or "").strip().lower()
    match = VARIABLE_NAME_RE.fullmatch(normalized)
    if match is None:
        raise VariableNameSchemaError(
            "Der Variablenname entspricht nicht dem Schema "
            "[Präfix_]abc123[_v1g1p1f1]."
        )

    suffix_text = match.group("suffixes") or ""
    suffixes: dict[str, int] = {}
    previous_rank = -1
    consumed = ""

    for suffix, number_text in SUFFIX_TOKEN_RE.findall(suffix_text):
        suffix = suffix.lower()
        consumed += f"{suffix}{number_text}"

        if suffix in suffixes:
            raise VariableNameSchemaError(
                f"Das Suffix '{suffix}' darf nur einmal vorkommen."
            )

        rank = SUFFIX_RANK[suffix]
        if rank < previous_rank:
            raise VariableNameSchemaError(
                "Die Suffixe müssen in der Reihenfolge v, g, p, f stehen."
            )
        previous_rank = rank

        number = int(number_text)
        if not 1 <= number <= 99:
            raise VariableNameSchemaError(
                "Suffixnummern müssen zwischen 1 und 99 liegen."
            )
        suffixes[suffix] = number

    if consumed != suffix_text:
        raise VariableNameSchemaError(
            "Die Variablensuffixe konnten nicht vollständig gelesen werden."
        )

    return ParsedVariableName(
        prefix=(match.group("prefix") or None),
        stem=match.group("stem").lower(),
        suffixes=suffixes,
    )


def normalize_variable_name(varname: str) -> str:
    """Validiert und liefert die kanonische, kleingeschriebene Form."""
    return parse_variable_name(varname).format()


def _family_variable_names(family_key: str) -> list[str]:
    """Lädt mögliche Mitglieder einer Familie und filtert sie anschließend exakt."""
    candidate_names = Variable.objects.filter(
        Q(varname__iexact=family_key)
        | Q(varname__istartswith=f"{family_key}_")
    ).values_list("varname", flat=True)

    family_names = []
    for candidate_name in candidate_names:
        try:
            parsed = parse_variable_name(candidate_name)
        except VariableNameSchemaError:
            continue
        if parsed.family_key == family_key:
            family_names.append(parsed.format())
    return family_names


def suggest_next_variable_name(
    source_varname: str,
    *,
    reserved_names: Iterable[str] = (),
) -> str:
    """
    Schlägt die nächste freie v-Nummer der Variablenfamilie vor.

    g-, p- und f-Suffixe der Ausgangsvariable bleiben erhalten. Der Präfix ist
    Bestandteil der Familie. Lücken werden nicht wiederverwendet; Ausgangspunkt
    ist immer die höchste vorhandene v-Nummer plus eins.
    """
    source = parse_variable_name(source_varname)
    family_names = _family_variable_names(source.family_key)

    highest_version = 0
    occupied_names = {name.casefold() for name in family_names}
    occupied_names.update(
        (name or "").strip().casefold()
        for name in reserved_names
        if (name or "").strip()
    )

    for family_name in family_names:
        parsed = parse_variable_name(family_name)
        highest_version = max(highest_version, parsed.version_number)

    next_version = highest_version + 1
    while next_version <= 99:
        candidate = source.with_version(next_version).format()
        if candidate.casefold() not in occupied_names:
            return candidate
        next_version += 1

    raise VariableNameSchemaError(
        f"Für die Variablenfamilie '{source.family_key}' ist keine freie "
        "Versionsnummer bis 99 verfügbar."
    )
