"""Сверка вершин и рёбер готовых SVG с PlantUML как текстовых данных."""

import re
import sys
from pathlib import Path
from xml.etree import ElementTree

OUTPUT = Path(__file__).resolve().parents[1] / "output"
LABEL_PATTERN = re.compile(r'^rectangle "([^"\n]*)" as (p\d+)', re.MULTILINE)
EDGE_PATTERN = re.compile(r"^(p\d+) --> (p\d+)$", re.MULTILINE)
EXAMPLE_STEMS = (
    "junit_junit_4.13.2",
    "org.slf4j_slf4j-simple_2.0.16",
    "org.apache.httpcomponents_httpclient_4.5.14",
)


def svg_topology(
    root: ElementTree.Element,
) -> tuple[set[str], set[tuple[str, str]]]:
    """Учесть старые и новые имена идентификаторов в SVG PlantUML."""
    aliases = {
        element.get("id", ""): element.get(
            "data-qualified-name", element.get("data-entity", "")
        )
        for element in root.iter() if element.get("class") == "entity"
    }
    edges = set()
    for element in root.iter():
        if element.get("class") == "link":
            left = element.get("data-entity-1", "")
            right = element.get("data-entity-2", "")
            edges.add((aliases.get(left, left), aliases.get(right, right)))
    return set(aliases.values()), edges


def verify_example(stem: str) -> None:
    """Сравнить подписи, идентификаторы узлов и направленные рёбра SVG."""
    source = (OUTPUT / f"{stem}.puml").read_text(encoding="utf-8")
    root = ElementTree.parse(OUTPUT / f"{stem}.svg").getroot()
    expected_labels = dict(LABEL_PATTERN.findall(source))
    expected_edges = set(EDGE_PATTERN.findall(source))
    texts = {
        "".join(element.itertext()) for element in root.iter()
        if element.tag.rsplit("}", 1)[-1] == "text"
    }
    entities, edges = svg_topology(root)
    if not set(expected_labels).issubset(texts):
        raise ValueError(f"Не все подписи присутствуют в SVG: {stem}")
    if set(expected_labels.values()) != entities:
        raise ValueError(f"Не совпали вершины SVG и PlantUML: {stem}")
    if expected_edges != edges:
        raise ValueError(f"Не совпали рёбра SVG и PlantUML: {stem}")
    print(f"{stem}: SVG, {len(entities)} вершин, {len(edges)} рёбер — OK")


def main() -> int:
    """Проверить три полученных изображения без запуска GUI."""
    try:
        for stem in EXAMPLE_STEMS:
            verify_example(stem)
    except (OSError, ValueError, ElementTree.ParseError) as error:
        print(f"Ошибка данных SVG: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
