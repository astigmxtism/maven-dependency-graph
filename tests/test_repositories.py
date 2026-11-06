"""Строгий формат файлового репозитория с именами из латинских букв."""

import tempfile
import unittest
from pathlib import Path

from maven_graph.errors import RepositoryError
from maven_graph.repositories import StaticRepository, load_test_repository


class RepositoryTests(unittest.TestCase):
    """Файл проверяется целиком, ошибки не превращаются в пустой граф."""

    def setUp(self) -> None:
        """Создать временный репозиторий для каждого теста."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "repository.json"

    def load(self, text: str) -> StaticRepository:
        """Передать JSON через реальный файловый интерфейс."""
        self.path.write_text(text, encoding="utf-8")
        return load_test_repository(self.path)

    def test_valid_bom_and_duplicate_edges(self) -> None:
        """BOM допустим, повтор одной дуги не создаёт кратное ребро."""
        repository = self.load('\ufeff{"A": ["B", "B"], "B": []}')
        self.assertEqual(repository.adjacency, {"A": ("B",), "B": ()})

    def test_invalid_repository_shapes(self) -> None:
        """Проверяются JSON, типы, имена и неопределённые ссылки."""
        texts = (
            "{", "[]", '{"A": "B"}', '{"a": []}',
            '{"A": [1]}', '{"A": ["B"]}', '{"A": [], "A": ["A"]}',
            '{"A": [], "B": {}}', '{"А": []}',
        )
        for text in texts:
            with self.subTest(text=text):
                with self.assertRaises(RepositoryError):
                    self.load(text)

    def test_missing_repository(self) -> None:
        """Удалённый после проверки INI файл даёт ошибку репозитория."""
        with self.assertRaises(RepositoryError):
            load_test_repository(self.path)
