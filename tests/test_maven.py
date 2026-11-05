"""Разбор POM, наследование, BOM, области и диагностика ошибок."""

import unittest

from maven_graph.errors import RepositoryError
from maven_graph.properties import Properties
from tests.pom_helpers import MemoryRepository, make_pom

PARENT_LINK = """<parent><groupId>example</groupId>
<artifactId>parent</artifactId><version>1</version></parent>"""
LIBRARY = """<dependency><groupId>example</groupId>
<artifactId>lib</artifactId><version>${lib.version}</version></dependency>"""
MANAGEMENT = (
    "<dependencyManagement><dependencies>{}</dependencies>"
    "</dependencyManagement>"
)


class MavenTests(unittest.TestCase):
    """Изолированные проверки самостоятельной реализации Maven-метаданных."""

    def test_direct_dependencies_and_plugin_isolation(self) -> None:
        """Вложенная зависимость плагина не считается зависимостью пакета."""
        body = (
            "<properties><lib.version>2</lib.version></properties>"
            f"<dependencies>{LIBRARY}</dependencies>"
            "<build><plugins><plugin><dependencies>"
            "<dependency><artifactId>ignored</artifactId></dependency>"
            "</dependencies></plugin></plugins></build>"
        )
        repository = MemoryRepository({"example:app:1": make_pom(body)})
        dependencies = repository.direct_dependencies("example:app:1")
        self.assertEqual(len(dependencies), 1)
        self.assertEqual(str(dependencies[0].coordinates), "example:lib:2")
        self.assertTrue(dependencies[0].is_runtime)
        repository.direct_dependencies("example:app:1")
        self.assertEqual(len(repository.requests), 1)
        expected_path = "example/app/1/app-1.pom"
        self.assertTrue(repository.requests[0].endswith(expected_path))

    def test_parent_properties_and_inherited_dependencies(self) -> None:
        """Дочернее свойство меняет унаследованную зависимость."""
        parent = make_pom(
            "<properties><lib.version>1</lib.version></properties>"
            f"<dependencies>{LIBRARY}</dependencies>", "parent"
        )
        child = (
            "<project>" + PARENT_LINK + "<artifactId>app</artifactId>"
            "<properties><lib.version>2</lib.version></properties></project>"
        )
        repository = MemoryRepository({
            "example:app:1": child, "example:parent:1": parent,
        })
        dependencies = repository.direct_dependencies("example:app:1")
        self.assertEqual(str(dependencies[0].coordinates), "example:lib:2")

    def test_management_does_not_add_edges(self) -> None:
        """dependencyManagement задаёт значения, но не добавляет зависимости."""
        body = (
            "<properties><lib.version>3</lib.version></properties>"
            + MANAGEMENT.format(LIBRARY)
        )
        repository = MemoryRepository({"example:app:1": make_pom(body)})
        self.assertEqual(repository.direct_dependencies("example:app:1"), ())

    def test_parent_management_supplies_version(self) -> None:
        """Отсутствующая версия берётся из dependencyManagement родителя."""
        parent = make_pom(
            "<properties><lib.version>3</lib.version></properties>"
            + MANAGEMENT.format(LIBRARY), "parent"
        )
        declaration = LIBRARY.replace("<version>${lib.version}</version>", "")
        body = PARENT_LINK + f"<dependencies>{declaration}</dependencies>"
        child = make_pom(body)
        repository = MemoryRepository({
            "example:app:1": child, "example:parent:1": parent,
        })
        dependencies = repository.direct_dependencies("example:app:1")
        self.assertEqual(str(dependencies[0].coordinates), "example:lib:3")

    def test_imported_bom_uses_its_own_properties(self) -> None:
        """Свойства импортированного BOM разрешаются в контексте BOM."""
        bom = make_pom(
            "<properties><lib.version>7</lib.version></properties>"
            + MANAGEMENT.format(LIBRARY), "bom"
        )
        imported = (
            "<dependency><groupId>example</groupId><artifactId>bom</artifactId>"
            "<version>1</version><type>pom</type>"
            "<scope>import</scope></dependency>"
        )
        declaration = LIBRARY.replace("<version>${lib.version}</version>", "")
        child = make_pom(
            "<properties><lib.version>99</lib.version></properties>"
            + MANAGEMENT.format(imported)
            + f"<dependencies>{declaration}</dependencies>"
        )
        repository = MemoryRepository({
            "example:app:1": child, "example:bom:1": bom,
        })
        dependencies = repository.direct_dependencies("example:app:1")
        self.assertEqual(str(dependencies[0].coordinates), "example:lib:7")

    def test_scopes_optional_and_exclusions(self) -> None:
        """Все прямые зависимости сохраняются вместе с Maven-атрибутами."""
        dependency = (
            "<dependency><groupId>example</groupId><artifactId>lib</artifactId>"
            "<version>1</version><scope>test</scope><optional>true</optional>"
            "<exclusions><exclusion><groupId>other</groupId>"
            "<artifactId>*</artifactId></exclusion></exclusions></dependency>"
        )
        body = f"<dependencies>{dependency}</dependencies>"
        repository = MemoryRepository({"example:app:1": make_pom(body)})
        item = repository.direct_dependencies("example:app:1")[0]
        self.assertEqual(item.scope, "test")
        self.assertTrue(item.optional)
        self.assertFalse(item.is_runtime)
        self.assertEqual(item.exclusions, frozenset({("other", "*")}))

    def test_invalid_xml_and_wrong_identity(self) -> None:
        """Синтаксическая ошибка и подменённый сервером POM диагностируются."""
        for text in ("<project>", "<html/>", make_pom(artifact="other")):
            with self.subTest(text=text):
                repository = MemoryRepository({"example:app:1": text})
                with self.assertRaises(RepositoryError):
                    repository.direct_dependencies("example:app:1")

    def test_unresolved_version_is_not_silently_skipped(self) -> None:
        """Неизвестное свойство нельзя скрыть пропуском зависимости."""
        repository = MemoryRepository({
            "example:app:1": make_pom(f"<dependencies>{LIBRARY}</dependencies>")
        })
        with self.assertRaisesRegex(RepositoryError, "lib.version"):
            repository.direct_dependencies("example:app:1")

    def test_parent_cycle(self) -> None:
        """Цикл в parent отличается от допустимого цикла зависимостей."""
        repository = MemoryRepository({
            "example:app:1": make_pom(PARENT_LINK),
            "example:parent:1": make_pom(PARENT_LINK, "parent"),
        })
        with self.assertRaisesRegex(RepositoryError, "Цикл parent/BOM"):
            repository.direct_dependencies("example:app:1")

    def test_property_cycle_and_unused_unknown_property(self) -> None:
        """Цикл обнаруживается; неиспользуемые build-свойства не мешают."""
        values = {"a": "${b}", "b": "${a}", "unused": "${env.X}"}
        properties = Properties(values)
        with self.assertRaisesRegex(RepositoryError, "Цикл свойств"):
            properties.expand("${a}")
        self.assertEqual(properties.expand("literal"), "literal")

    def test_namespaceless_empty_pom(self) -> None:
        """POM без namespace и без зависимостей допустим."""
        namespace = ' xmlns="http://maven.apache.org/POM/4.0.0"'
        text = make_pom().replace(namespace, "")
        repository = MemoryRepository({"example:app:1": text})
        self.assertEqual(repository.direct_dependencies("example:app:1"), ())
