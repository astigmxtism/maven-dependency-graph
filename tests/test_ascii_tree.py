"""Смысл ASCII-дерева: циклы, общие зависимости и вложенные ветви."""

import unittest

from maven_graph.ascii_tree import ascii_tree
from maven_graph.graph import DependencyGraph

DEEP_TREE_LENGTH = 1100


class AsciiTreeTests(unittest.TestCase):
    """Дерево сохраняет ссылки на повторные узлы без бесконечного вывода."""

    def test_diamond_marks_shared_node(self) -> None:
        """Общая зависимость не объявляется циклом."""
        graph = DependencyGraph("A", {
            "A": ("B", "C"), "B": ("D",), "C": ("D",), "D": (),
        })
        expected = "A\n+-- B\n|   \\-- D\n\\-- C\n    \\-- D [shared]"
        self.assertEqual(ascii_tree(graph), expected)

    def test_cycle_and_self_loop(self) -> None:
        """Петля и обратное ребро отмечаются как цикл текущего пути."""
        graph = DependencyGraph("A", {"A": ("A", "B"), "B": ("A",)})
        expected = "A\n+-- A [cycle]\n\\-- B\n    \\-- A [cycle]"
        self.assertEqual(ascii_tree(graph), expected)

    def test_leaf_and_deep_tree(self) -> None:
        """Корень и глубокая цепочка не требуют рекурсии вывода."""
        self.assertEqual(ascii_tree(DependencyGraph("A", {"A": ()})), "A")
        nodes = [f"node_{index}" for index in range(DEEP_TREE_LENGTH)]
        adjacency = {
            node: tuple(nodes[index + 1:index + 2])
            for index, node in enumerate(nodes)
        }
        output = ascii_tree(DependencyGraph(nodes[0], adjacency))
        self.assertEqual(len(output.splitlines()), DEEP_TREE_LENGTH)
        self.assertTrue(output.endswith(nodes[-1]))
