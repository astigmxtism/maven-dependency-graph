"""Приоритеты dependencyManagement и некорректные Maven-метаданные."""

import unittest

from maven_graph.errors import RepositoryError
from tests.pom_helpers import MemoryRepository, dependency_xml, make_pom

MANAGEMENT = (
    "<dependencyManagement><dependencies>{}</dependencies>"
    "</dependencyManagement>"
)
IMPORT = "<type>pom</type><scope>import</scope>"
LIBRARY = "<dependencies>" + dependency_xml(version="") + "</dependencies>"


class ManagementTests(unittest.TestCase):
    """Конфликты и ошибки, которые нельзя скрывать при получении графа."""

    def test_first_bom_and_local_override(self) -> None:
        """Первый BOM побеждает второй, локальное объявление побеждает оба."""
        imports = dependency_xml("first", extra=IMPORT)
        imports += dependency_xml("second", extra=IMPORT)
        poms = {
            "example:first:1": make_pom(
                MANAGEMENT.format(dependency_xml(version="2")), "first"
            ),
            "example:second:1": make_pom(
                MANAGEMENT.format(dependency_xml(version="3")), "second"
            ),
        }
        for local, expected in (("", "2"), (dependency_xml(version="4"), "4")):
            with self.subTest(expected=expected):
                body = MANAGEMENT.format(imports + local) + LIBRARY
                fixtures = poms | {"example:app:1": make_pom(body)}
                repository = MemoryRepository(fixtures)
                result = repository.direct_dependencies("example:app:1")
                self.assertEqual(result[0].coordinates.version, expected)

    def test_bom_cycle(self) -> None:
        """Рекурсивный импорт BOM завершается понятной ошибкой."""
        body = MANAGEMENT.format(dependency_xml("app", extra=IMPORT))
        repository = MemoryRepository({"example:app:1": make_pom(body)})
        with self.assertRaisesRegex(RepositoryError, "Цикл parent/BOM"):
            repository.direct_dependencies("example:app:1")

    def test_invalid_dependency_fields(self) -> None:
        """Пропуск версии и неизвестные scope/optional не игнорируются."""
        declarations = (
            dependency_xml(version=""),
            dependency_xml(extra="<scope>broken</scope>"),
            dependency_xml(extra="<optional>perhaps</optional>"),
        )
        for declaration in declarations:
            with self.subTest(declaration=declaration):
                body = f"<dependencies>{declaration}</dependencies>"
                repository = MemoryRepository({"example:app:1": make_pom(body)})
                with self.assertRaises(RepositoryError):
                    repository.direct_dependencies("example:app:1")

    def test_dtd_is_rejected(self) -> None:
        """Внешние определения сущностей не допускаются в POM."""
        text = '<!DOCTYPE project SYSTEM "file:///unused">' + make_pom()
        repository = MemoryRepository({"example:app:1": text})
        with self.assertRaisesRegex(RepositoryError, "DTD"):
            repository.direct_dependencies("example:app:1")

    def test_only_consumer_runtime_edges_are_followed(self) -> None:
        """test/provided/system/optional не переходят к потребителю пакета."""
        declarations = [
            dependency_xml(scope, extra=f"<scope>{scope}</scope>")
            for scope in ("compile", "runtime", "test", "provided", "system")
        ]
        declarations.append(
            dependency_xml("optional", extra="<optional>true</optional>")
        )
        body = "<dependencies>" + "".join(declarations) + "</dependencies>"
        repository = MemoryRepository({"example:app:1": make_pom(body)})
        links = repository.neighbors("example:app:1")
        self.assertEqual(
            [link.target for link in links],
            ["example:compile:1", "example:runtime:1"],
        )
