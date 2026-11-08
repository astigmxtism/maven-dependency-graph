"""Проверка интерпретации независимого текстового вывода Maven."""

import unittest

from tools.compare_maven import parse_tree


class ComparisonTests(unittest.TestCase):
    """Парсер сохраняет уровни дерева и удаляет только consumer-обёртку."""

    def test_siblings_and_classifier(self) -> None:
        """Тип и classifier не должны ошибочно становиться частью версии."""
        tree = (
            "comparison:consumer:jar:1\n"
            "\\- example:root:jar:1:compile\n"
            "   +- example:left:jar:2:compile\n"
            "   |  \\- example:leaf:test-jar:tests:3:runtime\n"
            "   \\- example:right:jar:4:compile\n"
        )
        expected = {
            "example:root:1": ("example:left:2", "example:right:4"),
            "example:left:2": ("example:leaf:3",),
            "example:leaf:3": (), "example:right:4": (),
        }
        self.assertEqual(parse_tree(tree), expected)

    def test_invalid_tree_is_not_a_successful_comparison(self) -> None:
        """Пустой или неизвестный формат Maven завершает проверку ошибкой."""
        for tree in ("", "consumer\nbroken\n", "consumer\n\\- broken\n"):
            with self.subTest(tree=tree):
                with self.assertRaises(ValueError):
                    parse_tree(tree)
