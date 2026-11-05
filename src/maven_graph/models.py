"""Модели POM и зависимостей без привязки к сети."""

from dataclasses import dataclass, field

from maven_graph.coordinates import Coordinates
from maven_graph.errors import ConfigError, RepositoryError
from maven_graph.properties import Properties

RUNTIME_SCOPES = {"compile", "runtime"}
DEPENDENCY_SCOPES = RUNTIME_SCOPES | {"test", "provided", "system", "import"}


@dataclass(frozen=True)
class Dependency:
    """Разрешённое объявление зависимости вместе с его Maven-атрибутами."""

    coordinates: Coordinates
    scope: str = "compile"
    optional: bool = False
    artifact_type: str = "jar"
    classifier: str = ""
    exclusions: frozenset[tuple[str, str]] = frozenset()

    @property
    def is_runtime(self) -> bool:
        """Нужна ли зависимость потребителю пакета во время исполнения."""
        return self.scope in RUNTIME_SCOPES and not self.optional


@dataclass(frozen=True)
class Declaration:
    """Сырые поля dependency; отсутствие поля допускает наследование."""

    values: dict[str, str] = field(default_factory=dict)
    exclusions: frozenset[tuple[str, str]] = frozenset()

    def key(self, properties: Properties) -> tuple[str, ...]:
        """Получить Maven-ключ groupId, artifactId, type, classifier."""
        defaults = {"type": "jar", "classifier": ""}
        fields = ("groupId", "artifactId", "type", "classifier")
        values = defaults | self.values
        return tuple(properties.expand(values.get(key, "")) for key in fields)

    def overlay(self, other: "Declaration") -> "Declaration":
        """Наложить дочернее объявление на унаследованные поля."""
        return Declaration(
            self.values | other.values, self.exclusions | other.exclusions
        )

    def expanded(self, properties: Properties) -> "Declaration":
        """Зафиксировать свойства импортируемого BOM в его контексте."""
        values = {
            key: properties.expand(value) for key, value in self.values.items()
        }
        exclusions = frozenset(
            (properties.expand(group), properties.expand(artifact))
            for group, artifact in self.exclusions
        )
        return Declaration(values, exclusions)


@dataclass
class PomModel:
    """Эффективные свойства и объявления опубликованного POM."""

    coordinates: Coordinates
    properties: dict[str, str]
    managed: dict[tuple[str, ...], Declaration]
    declarations: dict[tuple[str, ...], Declaration]


def parse_coordinates(value: str) -> Coordinates:
    """Показать ошибку координат внутри POM как ошибку репозитория."""
    try:
        return Coordinates.parse(value)
    except ConfigError as error:
        message = f"Некорректная зависимость POM: {value}"
        raise RepositoryError(message) from error


def resolve_dependency(
    declaration: Declaration,
    properties: Properties,
    managed: dict[tuple[str, ...], Declaration],
) -> Dependency:
    """Дополнить объявление из dependencyManagement и разрешить свойства."""
    key = declaration.key(properties)
    fallback = managed.get(key, Declaration())
    resolved = fallback.overlay(declaration).expanded(properties)
    values = resolved.values
    coordinate_fields = ("groupId", "artifactId", "version")
    coordinate_text = ":".join(values.get(key, "") for key in coordinate_fields)
    coordinates = parse_coordinates(coordinate_text)
    scope = values.get("scope", "compile")
    optional = values.get("optional", "false")
    if scope not in DEPENDENCY_SCOPES:
        raise RepositoryError(f"Некорректная область зависимости: {scope}")
    if optional not in {"true", "false"}:
        raise RepositoryError(f"Некорректное значение optional: {optional}")
    return Dependency(
        coordinates=coordinates,
        scope=scope,
        optional=optional == "true",
        artifact_type=values.get("type", "jar"),
        classifier=values.get("classifier", ""),
        exclusions=resolved.exclusions,
    )
