"""Получение эффективных зависимостей из опубликованных Maven POM."""

from collections.abc import Callable
from xml.etree import ElementTree

from maven_graph.config import validate_url
from maven_graph.coordinates import Coordinates
from maven_graph.errors import RepositoryError
from maven_graph.http import fetch_bytes
from maven_graph.models import (
    Declaration, Dependency, PomModel, parse_coordinates, resolve_dependency,
)
from maven_graph.pom import (
    model_properties, own_properties, parse_pom, read_declarations, text_at,
)
from maven_graph.properties import Properties

MAX_MODEL_DEPTH = 64


class MavenRepository:
    """Самостоятельный читатель Maven-репозитория с кешем POM в памяти."""

    def __init__(
        self, base_url: str, fetcher: Callable[[str], bytes] = fetch_bytes
    ) -> None:
        """Принять адрес репозитория и заменяемый сетевой транспорт."""
        self.base_url = validate_url(base_url)
        self.fetcher = fetcher
        self.cache: dict[str, PomModel] = {}
        self.active: set[str] = set()

    def model(self, coordinates: Coordinates) -> PomModel:
        """Загрузить POM, родителей и BOM, обнаруживая циклы метаданных."""
        package = str(coordinates)
        if package in self.cache:
            return self.cache[package]
        if package in self.active:
            raise RepositoryError(f"Цикл parent/BOM: {package}")
        if len(self.active) >= MAX_MODEL_DEPTH:
            raise RepositoryError("Слишком глубокая цепочка parent/BOM")
        if coordinates.version.endswith("-SNAPSHOT"):
            raise RepositoryError("Нужна release-версия, SNAPSHOT не поддержан")
        self.active.add(package)
        try:
            url = f"{self.base_url}/{coordinates.pom_path}"
            root = parse_pom(self.fetcher(url), package)
            parent = self.read_parent(root)
            model = self.assemble_model(root, coordinates, parent)
            self.cache[package] = model
            return model
        finally:
            self.active.remove(package)

    def read_parent(self, root: ElementTree.Element) -> PomModel | None:
        """Прочитать parent по координатам из того же удалённого репозитория."""
        parent = root.find("parent")
        if parent is None:
            return None
        properties = Properties(own_properties(root))
        fields = ("groupId", "artifactId", "version")
        values = (properties.expand(text_at(parent, key)) for key in fields)
        value = ":".join(values)
        return self.model(parse_coordinates(value))

    def assemble_model(
        self,
        root: ElementTree.Element,
        coordinates: Coordinates,
        parent: PomModel | None,
    ) -> PomModel:
        """Объединить наследование, свойства и управление зависимостями."""
        values = model_properties(root, coordinates, parent)
        properties = Properties(values)
        self.validate_identity(root, coordinates, parent, properties)
        managed = self.read_management(root, properties, parent)
        inherited = list(parent.declarations.values()) if parent else []
        local = read_declarations(root, "./dependencies/dependency")
        declarations: dict[tuple[str, ...], Declaration] = {}
        for item in inherited + local:
            key = item.key(properties)
            previous = declarations.get(key, Declaration())
            declarations[key] = previous.overlay(item)
        return PomModel(coordinates, values, managed, declarations)

    def validate_identity(
        self,
        root: ElementTree.Element,
        coordinates: Coordinates,
        parent: PomModel | None,
        properties: Properties,
    ) -> None:
        """Отклонить POM другого пакета, ошибочно отданный сервером."""
        group = parent.coordinates.group if parent else ""
        version = parent.coordinates.version if parent else ""
        fields = (
            text_at(root, "groupId", group),
            text_at(root, "artifactId"),
            text_at(root, "version", version),
        )
        value = ":".join(properties.expand(item) for item in fields)
        actual = parse_coordinates(value)
        if actual != coordinates:
            message = f"Ожидался POM {coordinates}, получен {actual}"
            raise RepositoryError(message)

    def read_management(
        self,
        root: ElementTree.Element,
        properties: Properties,
        parent: PomModel | None,
    ) -> dict[tuple[str, ...], Declaration]:
        """Импортировать BOM; локальное управление имеет высший приоритет."""
        inherited = dict(parent.managed) if parent else {}
        imported: dict[tuple[str, ...], Declaration] = {}
        local: dict[tuple[str, ...], Declaration] = {}
        path = "./dependencyManagement/dependencies/dependency"
        for item in read_declarations(root, path):
            scope = properties.expand(item.values.get("scope", ""))
            if scope == "import":
                self.import_bom(item, properties, inherited, imported)
            else:
                local[item.key(properties)] = item
        managed = inherited | imported
        for key, declaration in local.items():
            managed[key] = managed.get(key, Declaration()).overlay(declaration)
        return managed

    def import_bom(
        self,
        item: Declaration,
        properties: Properties,
        inherited: dict[tuple[str, ...], Declaration],
        imported: dict[tuple[str, ...], Declaration],
    ) -> None:
        """Зафиксировать контекст BOM; при нескольких BOM побеждает первый."""
        dependency = resolve_dependency(item, properties, inherited)
        if dependency.artifact_type != "pom":
            raise RepositoryError("scope=import требует type=pom")
        bom = self.model(dependency.coordinates)
        bom_properties = Properties(bom.properties)
        for declaration in bom.managed.values():
            resolved = declaration.expanded(bom_properties)
            imported.setdefault(resolved.key(bom_properties), resolved)

    def direct_dependencies(self, package: str) -> tuple[Dependency, ...]:
        """Вернуть все прямые объявления, включая test/provided/optional."""
        model = self.model(parse_coordinates(package))
        properties = Properties(model.properties)
        return tuple(
            resolve_dependency(item, properties, model.managed)
            for item in model.declarations.values()
        )
