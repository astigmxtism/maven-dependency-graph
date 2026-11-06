"""Рекурсивный BFS, циклы, глубокие цепочки и путь-зависимые exclusions."""

import unittest
from unittest.mock import patch

from maven_graph.errors import RepositoryError
from maven_graph.graph import Link, build_graph, is_excluded
from maven_graph.repositories import StaticRepository

DEEP_CHAIN_LENGTH = 1500


class RecordingRepository(StaticRepository):
    """Запоминать порядок обращений к пакетам для отличения BFS от DFS."""

    def __init__(self, adjacency: dict[str, list[str]]) -> None:
        """Создать репозиторий и журнал обращений."""
        super().__init__(adjacency)
        self.requests: list[str] = []

    def neighbors(self, package: str) -> tuple[Link, ...]:
        """Записать запрос и вернуть стандартный список соседей."""
        self.requests.append(package)
        return super().neighbors(package)


class ExclusionRepository:
    """Одна вершина достижима путями с разными исключениями."""

    def __init__(self, alternate: bool = True) -> None:
        """Выбрать наличие обходного пути без запрета."""
        self.alternate = alternate

    def neighbors(self, package: str) -> tuple[Link, ...]:
        """Выдать рёбра ромба, где запрет действует только на одной ветви."""
        blocked = frozenset({("example", "leaf")})
        links = (Link("example:shared:1", blocked),)
        if self.alternate:
            links += (Link("example:branch:1"),)
        adjacency = {
            "example:root:1": links,
            "example:branch:1": (Link("example:shared:1"),),
            "example:shared:1": (Link("example:leaf:1"),),
            "example:leaf:1": (),
        }
        return adjacency[package]


class GraphTests(unittest.TestCase):
    """Поведение алгоритма на структурно разных графах."""

    def test_breadth_first_order_and_diamond(self) -> None:
        """Весь уровень B,C посещается до D; общая вершина читается один раз."""
        repository = RecordingRepository({
            "A": ["B", "C"], "B": ["D"], "C": ["D"], "D": [],
        })
        graph = build_graph("A", repository)
        self.assertEqual(repository.requests, ["A", "B", "C", "D"])
        self.assertEqual(graph.adjacency["B"], ("D",))
        self.assertEqual(graph.adjacency["C"], ("D",))
        self.assertEqual(graph.edge_count, 4)

    def test_cycle_and_self_loop_keep_edges(self) -> None:
        """Циклические рёбра сохраняются без повторного раскрытия вершин."""
        repository = RecordingRepository({
            "A": ["A", "B"], "B": ["C"], "C": ["A"],
        })
        graph = build_graph("A", repository)
        self.assertEqual(repository.requests, ["A", "B", "C"])
        self.assertEqual(graph.adjacency["A"], ("A", "B"))
        self.assertEqual(graph.adjacency["C"], ("A",))
        self.assertEqual(graph.edge_count, 4)

    def test_disconnected_and_leaf(self) -> None:
        """Недостижимые компоненты не попадают в прямой граф."""
        repository = StaticRepository({"A": [], "B": ["C"], "C": []})
        graph = build_graph("A", repository)
        self.assertEqual(graph.adjacency, {"A": ()})
        self.assertEqual(graph.edge_count, 0)

    def test_deep_chain_avoids_python_recursion_limit(self) -> None:
        """Порционная рекурсия выдерживает более тысячи уровней BFS."""
        nodes = [f"node_{index}" for index in range(DEEP_CHAIN_LENGTH)]
        adjacency = {
            node: nodes[index + 1:index + 2]
            for index, node in enumerate(nodes)
        }
        graph = build_graph(nodes[0], StaticRepository(adjacency))
        self.assertEqual(len(graph.adjacency), DEEP_CHAIN_LENGTH)
        self.assertEqual(graph.edge_count, DEEP_CHAIN_LENGTH - 1)

    def test_exclusions_are_specific_to_each_path(self) -> None:
        """Запрет одной ветви не скрывает допустимую зависимость другой."""
        graph = build_graph("example:root:1", ExclusionRepository())
        self.assertIn("example:leaf:1", graph.adjacency)
        targets = graph.adjacency["example:shared:1"]
        self.assertEqual(targets, ("example:leaf:1",))

    def test_excluded_node_is_not_loaded(self) -> None:
        """Без обходного пути исключённая зависимость не попадает в граф."""
        graph = build_graph("example:root:1", ExclusionRepository(False))
        self.assertNotIn("example:leaf:1", graph.adjacency)
        self.assertEqual(graph.adjacency["example:shared:1"], ())

    def test_wildcard_exclusions(self) -> None:
        """Звёздочка поддерживается независимо в группе и артефакте."""
        for rule in (("*", "lib"), ("example", "*"), ("*", "*")):
            with self.subTest(rule=rule):
                self.assertTrue(is_excluded("example:lib:1", frozenset({rule})))
        self.assertFalse(
            is_excluded("example:lib:1", frozenset({("different", "lib")}))
        )

    def test_unknown_root_and_graph_limit(self) -> None:
        """Отсутствующий корень и превышение лимита имеют понятные ошибки."""
        repository = StaticRepository({"A": ["B"], "B": []})
        with self.assertRaisesRegex(RepositoryError, "отсутствует"):
            build_graph("C", repository)
        with patch("maven_graph.graph.MAX_GRAPH_NODES", 1):
            with self.assertRaisesRegex(RepositoryError, "больше"):
                build_graph("A", repository)
