"""Проверка публичного CLI и кодов завершения."""

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from maven_graph.cli import EXIT_ERROR, main
from maven_graph.coordinates import Coordinates
from maven_graph.models import Dependency


class CliTests(unittest.TestCase):
    """Контракт CLI второго этапа."""

    def test_direct_dependencies_are_printed(self) -> None:
        """CLI отображает разрешённые координаты и область зависимости."""
        output = io.StringIO()
        coordinates = Coordinates("org.hamcrest", "hamcrest-core", "1.3")
        dependency = Dependency(coordinates)
        with patch("maven_graph.cli.MavenRepository") as repository:
            instance = repository.return_value
            instance.direct_dependencies.return_value = [dependency]
            with redirect_stdout(output):
                code = main([])
        self.assertEqual(code, 0)
        expected = "org.hamcrest:hamcrest-core:1.3 [compile]"
        self.assertIn(expected, output.getvalue())
        self.assertNotIn("test_mode=", output.getvalue())

    def test_error_is_sent_to_stderr(self) -> None:
        """Ошибка конфигурации не создаёт traceback."""
        output = io.StringIO()
        with redirect_stderr(output):
            code = main(["--config", "does-not-exist.ini"])
        self.assertEqual(code, EXIT_ERROR)
        self.assertIn("Ошибка:", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())
