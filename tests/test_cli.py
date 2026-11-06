"""Проверка публичного CLI и кодов завершения."""

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from maven_graph.cli import EXIT_ERROR, main
from maven_graph.repositories import StaticRepository


class CliTests(unittest.TestCase):
    """Контракт CLI третьего этапа."""

    def test_graph_is_printed(self) -> None:
        """CLI отображает вершины и рёбра построенного графа."""
        output = io.StringIO()
        repository = StaticRepository({
            "junit:junit:4.13.2": ["org.hamcrest:hamcrest-core:1.3"],
            "org.hamcrest:hamcrest-core:1.3": [],
        })
        factory = "maven_graph.cli.create_repository"
        with patch(factory, return_value=repository):
            with redirect_stdout(output):
                code = main([])
        self.assertEqual(code, 0)
        expected = "junit:junit:4.13.2 -> org.hamcrest:hamcrest-core:1.3"
        self.assertIn(expected, output.getvalue())
        self.assertIn("Вершин: 2; рёбер: 1", output.getvalue())
        self.assertNotIn("test_mode=", output.getvalue())

    def test_error_is_sent_to_stderr(self) -> None:
        """Ошибка конфигурации не создаёт traceback."""
        output = io.StringIO()
        with redirect_stderr(output):
            code = main(["--config", "does-not-exist.ini"])
        self.assertEqual(code, EXIT_ERROR)
        self.assertIn("Ошибка:", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())
