"""Все пользовательские параметры визуализации проверяются через INI."""

import tempfile
import unittest
from pathlib import Path

from maven_graph.config import Settings, load_config
from maven_graph.errors import ConfigError
from tests.test_config import VALID_INI


class DisplayConfigTests(unittest.TestCase):
    """Валидация адреса рендера, пути и обоих логических режимов."""

    def setUp(self) -> None:
        """Создать временный INI в папке с известным базовым путём."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.path = self.folder / "config.ini"

    def load(self, options: str) -> Settings:
        """Добавить секцию визуализации и прочитать полный INI."""
        text = VALID_INI + "\n[visualization]\n" + options
        self.path.write_text(text, encoding="utf-8")
        return load_config(self.path)

    def test_paths_and_offline_defaults(self) -> None:
        """Путь разрешается от INI; render=false выключает показ."""
        settings = self.load("output_dir = diagrams\nrender = false\n")
        self.assertEqual(settings.display.output_dir, self.folder / "diagrams")
        self.assertFalse(settings.display.render)
        self.assertFalse(settings.display.open_image)

    def test_invalid_values_for_all_visualization_keys(self) -> None:
        """Для каждого параметра выдаётся адресное сообщение об ошибке."""
        cases = (
            ("output_dir =\n", "output_dir"),
            ("output_dir = bad\0name\n", "output_dir"),
            ("plantuml_url = file:///x\n", "plantuml_url"),
            ("render = perhaps\n", "render"),
            ("open_image = perhaps\n", "open_image"),
            ("render = false\nopen_image = true\n", "open_image"),
            ("unknown = value\n", "unknown"),
        )
        for options, key in cases:
            with self.subTest(key=key):
                with self.assertRaisesRegex(ConfigError, key):
                    self.load(options)

    def test_output_directory_cannot_be_existing_file(self) -> None:
        """Нельзя выбрать сам INI в качестве папки результатов."""
        with self.assertRaisesRegex(ConfigError, "output_dir"):
            self.load("output_dir = config.ini\n")
