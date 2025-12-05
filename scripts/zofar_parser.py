# questions/zofar_parser.py

import re
import xml.etree.ElementTree as ET


ZOFAR_NS = "http://www.his.de/zofar/xml/questionnaire"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


def localname(tag: str) -> str:
    """
    Gibt den lokalen Tag-Namen zurück, egal ob der Tag z.B.
    'zofar:question' oder '{namespace}question' heißt.
    """
    return tag.split('}')[-1].split(':')[-1]


def _ensure_namespaces(xml_str: str) -> str:
    """
    Stellt sicher, dass auf <zofar:page ...> die relevanten Namespace-
    Deklarationen vorhanden sind.

    - Wenn 'xmlns:zofar' fehlt, wird er ergänzt.
    - Wenn 'xsi:' verwendet wird, aber 'xmlns:xsi' fehlt, wird er ergänzt.
    """
    xml_str = xml_str.strip()
    if not xml_str:
        return xml_str

    # nur das erste <zofar:page ...> finden
    match = re.search(r"<\s*zofar:page\b([^>]*)>", xml_str)
    if not match:
        return xml_str

    attrs = match.group(1)

    if "xmlns:zofar" not in attrs:
        attrs += f' xmlns:zofar="{ZOFAR_NS}"'

    if "xsi:" in xml_str and "xmlns:xsi" not in attrs:
        attrs += f' xmlns:xsi="{XSI_NS}"'

    new_first_tag = f"<zofar:page{attrs}>"
    xml_str = xml_str[:match.start()] + new_first_tag + xml_str[match.end():]
    return xml_str


def parse_zofar_page(xml_str: str) -> dict:
    """
    Parst eine einzelne <zofar:page> und gibt ein Dict mit:
    - pagename
    - questiontext
    - question_type
    - answer_options
    - transitions
    zurück.
    """
    xml_str = xml_str.strip()
    if not xml_str:
        raise ValueError("Leerer XML-String")

    # Namespaces ergänzen, falls im Snippet nicht gesetzt
    xml_str = _ensure_namespaces(xml_str)

    root = ET.fromstring(xml_str)

    # 1) pagename
    pagename = root.attrib.get("uid", "")

    # 2) questiontext
    questiontext = ""
    for el in root.iter():
        if localname(el.tag) == "question":
            questiontext = "".join(el.itertext()).strip()
            if questiontext:
                break

    # 3) question_type aus direction im responseDomain
    direction = ""
    for el in root.iter():
        if localname(el.tag) == "responseDomain":
            direction = el.attrib.get("direction", "")
            break

    if direction == "vertical":
        question_type = "single_vertical"
    elif direction == "horizontal":
        question_type = "single_horizontal"
    else:
        question_type = "single"  # Fallback für jetzt

    # 4) answer_options
    answer_options = []
    for el in root.iter():
        if localname(el.tag) == "answerOption":
            answer_options.append(
                {
                    "uid": el.attrib.get("uid"),
                    "value": el.attrib.get("value"),
                    "label": el.attrib.get("label"),
                }
            )

    # 5) transitions
    transitions = []
    for el in root.iter():
        if localname(el.tag) == "transition":
            transitions.append(
                {
                    "target": el.attrib.get("target"),
                    "condition": el.attrib.get("condition"),
                }
            )

    return {
        "pagename": pagename,
        "questiontext": questiontext,
        "question_type": question_type,
        "answer_options": answer_options,
        "transitions": transitions,
    }
