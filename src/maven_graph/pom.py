"""Разбор только значимых разделов XML POM средствами ElementTree."""

from xml.etree import ElementTree

from maven_graph.coordinates import Coordinates
from maven_graph.errors import RepositoryError
from maven_graph.models import Declaration, PomModel

DEPENDENCY_FIELDS = (
    "groupId", "artifactId", "version", "scope", "optional",
    "type", "classifier",
)


def parse_pom(data: bytes, package: str) -> ElementTree.Element:
    """Разобрать XML и нормализовать namespace Maven."""
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise RepositoryError(f"DTD и ENTITY не поддерживаются: {package}")
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError as error:
        message = f"Некорректный XML POM {package}: {error}"
        raise RepositoryError(message) from error
    for element in root.iter():
        element.tag = element.tag.rsplit("}", 1)[-1]
    if root.tag != "project":
        message = f"Корневой элемент POM должен быть project: {package}"
        raise RepositoryError(message)
    return root


def text_at(root: ElementTree.Element, path: str, default: str = "") -> str:
    """Прочитать текст поля, учитывая пустые XML-элементы."""
    return (root.findtext(path) or default).strip()


def own_properties(root: ElementTree.Element) -> dict[str, str]:
    """Прочитать свойства только текущего проекта, исключая profiles."""
    return {
        element.tag: (element.text or "").strip()
        for element in root.findall("./properties/*")
    }


def coordinate_properties(coordinates: Coordinates) -> dict[str, str]:
    """Определить project.*, pom.* и короткие координатные свойства."""
    values = {
        "groupId": coordinates.group,
        "artifactId": coordinates.artifact,
        "version": coordinates.version,
    }
    return {
        prefix + name: value
        for prefix in ("", "project.", "pom.")
        for name, value in values.items()
    }


def model_properties(
    root: ElementTree.Element,
    coordinates: Coordinates,
    parent: PomModel | None,
) -> dict[str, str]:
    """Наследовать сырые свойства и наложить значения дочернего проекта."""
    values = dict(parent.properties) if parent else {}
    values.update(own_properties(root))
    values.update(coordinate_properties(coordinates))
    if parent:
        parent_values = coordinate_properties(parent.coordinates)
        for prefix in ("parent.", "project.parent.", "pom.parent."):
            for name in ("groupId", "artifactId", "version"):
                values[prefix + name] = parent_values[name]
    return values


def read_declarations(
    root: ElementTree.Element, path: str
) -> list[Declaration]:
    """Извлечь зависимости только по точному пути, не из plugins/profiles."""
    declarations = []
    for element in root.findall(path):
        values = {
            key: text_at(element, key)
            for key in DEPENDENCY_FIELDS
            if text_at(element, key)
        }
        exclusions = frozenset(
            (text_at(item, "groupId"), text_at(item, "artifactId"))
            for item in element.findall("./exclusions/exclusion")
        )
        declarations.append(Declaration(values, exclusions))
    return declarations
