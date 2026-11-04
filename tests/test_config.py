"""Проверка каждого параметра INI и ошибок файлового ввода."""

import tempfile
import unittest
from pathlib import Path

from maven_graph.config import Settings, load_config
from maven_graph.errors import ConfigError

REPOSITORY_URL = "https://repo.maven.apache.org/maven2"
VALID_INI = """[settings]
package = junit:junit:4.13.2
repository = https://repo.maven.apache.org/maven2
test_mode = false
ascii_tree = true
"""


class ConfigTests(unittest.TestCase):
    """Проверки схемы, режимов, координат и адреса репозитория."""

    def setUp(self) -> None:
        """Создать изолированную папку для входных файлов."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.config = self.folder / "config.ini"

    def load(self, text: str = VALID_INI) -> Settings:
        """Записать входной INI и вызвать публичный загрузчик."""
        self.config.write_text(text, encoding="utf-8")
        return load_config(self.config)

    def test_valid_settings(self) -> None:
        """Все четыре значения доступны после проверки."""
        settings = self.load()
        self.assertEqual(settings.package, "junit:junit:4.13.2")
        self.assertFalse(settings.test_mode)
        self.assertTrue(settings.ascii_tree)
        self.assertEqual(
            settings.repository, "https://repo.maven.apache.org/maven2"
        )

    def test_invalid_values_for_every_parameter(self) -> None:
        """Опечатка в каждом из четырёх параметров даёт адресную ошибку."""
        cases = (
            ("junit:junit:4.13.2", "junit", "package"),
            ("junit:junit:4.13.2", "a:b:[1,2)", "package"),
            (REPOSITORY_URL, "ftp://host", "repository"),
            (REPOSITORY_URL, "https://", "repository"),
            (REPOSITORY_URL, "https://a:xx", "repository"),
            ("test_mode = false", "test_mode = maybe", "test_mode"),
            ("ascii_tree = true", "ascii_tree = maybe", "ascii_tree"),
        )
        for old, new, key in cases:
            with self.subTest(key=key, value=new):
                with self.assertRaisesRegex(ConfigError, key):
                    self.load(VALID_INI.replace(old, new))

    def test_missing_and_unknown_keys(self) -> None:
        """Ни один обязательный ключ нельзя пропустить или переименовать."""
        for key in ("package", "repository", "test_mode", "ascii_tree"):
            lines = VALID_INI.splitlines()
            text = "\n".join(line for line in lines if not line.startswith(key))
            with self.subTest(key=key):
                with self.assertRaisesRegex(ConfigError, key):
                    self.load(text)
        with self.assertRaisesRegex(ConfigError, "неизвестные"):
            self.load(VALID_INI + "unexpected = value\n")

    def test_broken_ini_and_sections(self) -> None:
        """Повторы, DEFAULT, посторонняя секция и плохой синтаксис запрещены."""
        texts = (
            VALID_INI + "package = another\n",
            VALID_INI.replace("[settings]", "[other]"),
            "[DEFAULT]\nother = value\n" + VALID_INI,
            "not an INI",
        )
        for text in texts:
            with self.subTest(text=text):
                with self.assertRaises(ConfigError):
                    self.load(text)

    def test_missing_file_and_directory(self) -> None:
        """Отсутствующий файл и каталог вместо файла дают ConfigError."""
        for path in (self.config, self.folder):
            with self.subTest(path=path):
                with self.assertRaises(ConfigError):
                    load_config(path)

    def test_test_repository_relative_to_ini(self) -> None:
        """Относительный путь отсчитывается от INI, а не от cwd."""
        graph = self.folder / "graph.json"
        graph.write_text('{"A": []}', encoding="utf-8")
        text = VALID_INI.replace("junit:junit:4.13.2", "A")
        text = text.replace("test_mode = false", "test_mode = yes")
        text = text.replace("https://repo.maven.apache.org/maven2", graph.name)
        settings = self.load(text)
        self.assertEqual(settings.repository, str(graph.resolve()))
        with self.assertRaisesRegex(ConfigError, "package"):
            self.load(text.replace("package = A", "package = a"))
        with self.assertRaisesRegex(ConfigError, "repository"):
            self.load(text.replace(graph.name, "missing.json"))

    def test_utf8_bom_and_boolean_forms(self) -> None:
        """BOM и стандартные значения ConfigParser поддерживаются."""
        text = VALID_INI.replace("false", "OFF").replace("true", "1")
        self.assertTrue(self.load("\ufeff" + text).ascii_tree)

    def test_invalid_encoding(self) -> None:
        """Некорректная кодировка не приводит к необработанной ошибке."""
        self.config.write_bytes(b"\xff\xfe\x00")
        with self.assertRaises(ConfigError):
            load_config(self.config)
