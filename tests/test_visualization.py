"""Экспорт и проверка SVG как XML; реальный просмотрщик не запускается."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from maven_graph.config import DisplaySettings
from maven_graph.errors import RepositoryError, VisualizationError
from maven_graph.graph import DependencyGraph
from maven_graph.visualization import export_graph, open_image, render_svg

VALID_SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><text>A</text></svg>'
FETCH_TARGET = "maven_graph.visualization.fetch_bytes"
OPENER_TARGET = "maven_graph.visualization.webbrowser.open"


class VisualizationTests(unittest.TestCase):
    """Файловые и сетевые ошибки не скрывают сохранённый исходник диаграммы."""

    def setUp(self) -> None:
        """Выделить временную папку для результатов теста."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.graph = DependencyGraph("A", {"A": ()})

    def test_offline_export_requires_no_renderer(self) -> None:
        """При render=false записывается только PlantUML без сетевых вызовов."""
        settings = DisplaySettings(self.folder, render=False, open_image=False)
        with patch(FETCH_TARGET) as fetcher:
            files = export_graph(self.graph, settings)
        fetcher.assert_not_called()
        self.assertIn("@startuml", files.source.read_text(encoding="utf-8"))
        self.assertIsNone(files.image)

    def test_rendered_svg_is_saved(self) -> None:
        """Успешный ответ сохраняется вместе с исходником."""
        settings = DisplaySettings(self.folder, open_image=False)
        with patch(FETCH_TARGET, return_value=VALID_SVG):
            files = export_graph(self.graph, settings, reverse=True)
        self.assertEqual(files.image.read_bytes(), VALID_SVG)
        self.assertEqual(files.source.name, "A-reverse.puml")

    def test_invalid_svg_is_rejected(self) -> None:
        """HTML и повреждённый XML не выдаются за изображение."""
        for response in (b"<html/>", b"<svg>"):
            with self.subTest(response=response):
                with patch(FETCH_TARGET, return_value=response):
                    with self.assertRaises(VisualizationError):
                        render_svg("source", "https://example.org")

    def test_network_failure_keeps_plantuml(self) -> None:
        """Даже при недоступном сервере текст диаграммы остаётся на диске."""
        settings = DisplaySettings(self.folder, open_image=False)
        with patch(FETCH_TARGET, side_effect=RepositoryError("timeout")):
            with self.assertRaisesRegex(VisualizationError, "PlantUML"):
                export_graph(self.graph, settings)
        self.assertTrue((self.folder / "A.puml").is_file())
        self.assertFalse((self.folder / "A.svg").exists())

    def test_write_error_is_readable(self) -> None:
        """Ошибка доступа к папке преобразуется в ошибку приложения."""
        with patch.object(Path, "mkdir", side_effect=PermissionError("denied")):
            with self.assertRaisesRegex(VisualizationError, "сохранить"):
                export_graph(self.graph, DisplaySettings(self.folder))

    def test_open_uses_local_file_uri_without_launching_gui(self) -> None:
        """Показ проверяется заменой системного вызова на mock."""
        path = self.folder / "with space.svg"
        with patch(OPENER_TARGET, return_value=True) as opener:
            open_image(path)
        opener.assert_called_once_with(path.resolve().as_uri(), new=2)
        with patch(OPENER_TARGET, return_value=False):
            with self.assertRaises(VisualizationError):
                open_image(path)
