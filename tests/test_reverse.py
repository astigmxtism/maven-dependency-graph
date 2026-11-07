"""Обратные зависимости по полному тестовому графу и Maven-подграфу."""

import unittest

from maven_graph.config import ReverseSettings, Settings
from maven_graph.errors import RepositoryError
from maven_graph.operations import (
    analyze_graph, build_reverse_graph, reverse_dependents,
)
from maven_graph.repositories import StaticRepository
from tests.pom_helpers import (
    BASE_URL, MemoryRepository, dependency_xml, make_pom,
)


class ReverseTests(unittest.TestCase):
    """Транспонирование сохраняет циклы и использует порядок BFS."""

    def test_diamond_has_direct_and_transitive_dependents(self) -> None:
        """D нужен B и C непосредственно, A — транзитивно."""
        adjacency = {"A": ("B", "C"), "B": ("D",), "C": ("D",), "D": ()}
        graph = build_reverse_graph("D", adjacency)
        self.assertEqual(graph.adjacency["D"], ("B", "C"))
        self.assertEqual(reverse_dependents(graph), ("B", "C", "A"))
        self.assertEqual(graph.edge_count, 4)

    def test_full_test_repository_is_used(self) -> None:
        """Поиск видит родителей из другой компоненты прямого обхода цели."""
        source = StaticRepository({
            "A": ["B"], "B": [], "C": ["B"], "D": ["C"], "E": [],
        })
        settings = Settings(
            "B", "unused.json", True, True, ReverseSettings(True)
        )
        graph = analyze_graph(settings, source)
        self.assertEqual(reverse_dependents(graph), ("A", "C", "D"))
        self.assertNotIn("E", graph.adjacency)

    def test_cycle_and_self_loop_exclude_root_from_list(self) -> None:
        """Корень не становится собственной обратной зависимостью в списке."""
        adjacency = {"A": ("A", "B"), "B": ("C",), "C": ("A",)}
        graph = build_reverse_graph("A", adjacency)
        self.assertEqual(reverse_dependents(graph), ("C", "B"))
        self.assertIn("A", graph.adjacency["A"])
        self.assertEqual(graph.edge_count, 4)

    def test_isolated_and_missing_target(self) -> None:
        """Пустой ответ отличается от отсутствующего в репозитории пакета."""
        graph = build_reverse_graph("A", {"A": ()})
        self.assertEqual(reverse_dependents(graph), ())
        with self.assertRaisesRegex(RepositoryError, "отсутствует"):
            build_reverse_graph("B", {"A": ()})

    def test_maven_reverse_target_in_analyzed_closure(self) -> None:
        """Для Maven используется собранный граф выбранного корневого GAV."""
        body = "<dependencies>" + dependency_xml() + "</dependencies>"
        repository = MemoryRepository({
            "example:app:1": make_pom(body),
            "example:lib:1": make_pom(artifact="lib"),
        })
        settings = Settings(
            "example:app:1", BASE_URL, False, True,
            ReverseSettings(True, "example:lib:1"),
        )
        graph = analyze_graph(settings, repository)
        self.assertEqual(graph.root, "example:lib:1")
        self.assertEqual(reverse_dependents(graph), ("example:app:1",))
