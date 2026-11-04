"""Проверка публичного CLI и кодов завершения."""

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout

from maven_graph.cli import EXIT_ERROR, main


class CliTests(unittest.TestCase):
    """Контракт CLI первого этапа."""

    def test_default_config_prints_all_settings(self) -> None:
        """Значения выводятся в формате ключ=значение."""
        output = io.StringIO()
        with redirect_stdout(output):
            code = main([])
        self.assertEqual(code, 0)
        self.assertEqual(len(output.getvalue().splitlines()), 4)
        self.assertIn("test_mode=false", output.getvalue())
        self.assertIn("ascii_tree=true", output.getvalue())

    def test_error_is_sent_to_stderr(self) -> None:
        """Ошибка конфигурации не создаёт traceback."""
        output = io.StringIO()
        with redirect_stderr(output):
            code = main(["--config", "does-not-exist.ini"])
        self.assertEqual(code, EXIT_ERROR)
        self.assertIn("Ошибка:", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())
