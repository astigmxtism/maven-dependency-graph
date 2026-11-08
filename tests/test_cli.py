"""Проверка публичного CLI и кодов завершения."""

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from maven_graph.cli import EXIT_ERROR, main, present_graph
from maven_graph.config import DisplaySettings, Settings
from maven_graph.graph import DependencyGraph
from maven_graph.repositories import StaticRepository
from maven_graph.visualization import VisualizationFiles


class CliTests(unittest.TestCase):
    """Контракт финального CLI; системный просмотрщик всегда заменён mock."""

    def test_graph_is_printed(self) -> None:
        """CLI отображает вершины и рёбра построенного графа."""
        output = io.StringIO()
        repository = StaticRepository({
            "junit:junit:4.13.2": ["org.hamcrest:hamcrest-core:1.3"],
            "org.hamcrest:hamcrest-core:1.3": [],
        })
        factory = "maven_graph.cli.create_repository"
        files = VisualizationFiles(Path("output/graph.puml"))
        with (
            patch(factory, return_value=repository),
            patch("maven_graph.cli.export_graph", return_value=files),
        ):
            with redirect_stdout(output):
                code = main([])
        self.assertEqual(code, 0)
        expected = "\\-- org.hamcrest:hamcrest-core:1.3"
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

    def test_ascii_can_be_disabled(self) -> None:
        """ascii_tree=false убирает дерево, оставляя сводку и результат."""
        graph = DependencyGraph("A", {"A": ("B",), "B": ()})
        settings = Settings("A", "unused", True, False)
        files = VisualizationFiles(Path("graph.puml"))
        output = io.StringIO()
        with patch("maven_graph.cli.export_graph", return_value=files):
            with redirect_stdout(output):
                present_graph(graph, settings)
        self.assertNotIn("\\-- B", output.getvalue())
        self.assertIn("PlantUML:", output.getvalue())

    def test_image_opening_follows_ini_flag(self) -> None:
        """Вызов показа выполняется только при open_image=true."""
        graph = DependencyGraph("A", {"A": ()})
        files = VisualizationFiles(Path("graph.puml"), Path("graph.svg"))
        for enabled in (False, True):
            display = DisplaySettings(open_image=enabled)
            settings = Settings("A", "unused", True, False, display=display)
            with (
                self.subTest(enabled=enabled),
                patch("maven_graph.cli.export_graph", return_value=files),
                patch("maven_graph.cli.open_image") as opener,
                redirect_stdout(io.StringIO()),
            ):
                present_graph(graph, settings)
                self.assertEqual(opener.call_count, int(enabled))
