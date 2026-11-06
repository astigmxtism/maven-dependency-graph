"""Файловый тестовый репозиторий и выбор источника по INI."""

import json
import re
from pathlib import Path

from maven_graph.config import Settings
from maven_graph.coordinates import TEST_PACKAGE_PATTERN
from maven_graph.errors import RepositoryError
from maven_graph.graph import Link, NeighborSource
from maven_graph.maven import MavenRepository

MAX_TEST_REPOSITORY_BYTES = 4 * 1024 * 1024


class StaticRepository:
    """Конечный граф в памяти для прямого и обратного обхода."""

    def __init__(
        self, adjacency: dict[str, list[str] | tuple[str, ...]]
    ) -> None:
        """Скопировать входной граф, убрав повторные рёбра."""
        self.adjacency = {
            node: tuple(dict.fromkeys(targets))
            for node, targets in adjacency.items()
        }

    def neighbors(self, package: str) -> tuple[Link, ...]:
        """Вернуть соседей либо сообщить об отсутствии выбранного пакета."""
        if package not in self.adjacency:
            raise RepositoryError(f"Пакет отсутствует в репозитории: {package}")
        return tuple(Link(target) for target in self.adjacency[package])


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Запретить повторные JSON-ключи вместо потери части входных данных."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise RepositoryError(f"Повторный пакет в JSON: {key}")
        result[key] = value
    return result


def validate_test_name(name: object) -> None:
    """Проверить, что имя состоит из больших латинских букв."""
    if not isinstance(name, str):
        raise RepositoryError(f"Имя пакета должно быть строкой: {name!r}")
    if not re.fullmatch(TEST_PACKAGE_PATTERN, name):
        raise RepositoryError(f"Неверное имя тестового пакета: {name!r}")


def validate_adjacency(data: object) -> dict[str, list[str]]:
    """Проверить весь тестовый граф, включая недостижимые компоненты."""
    if not isinstance(data, dict):
        raise RepositoryError("Тестовый репозиторий должен быть JSON-объектом")
    for node, targets in data.items():
        validate_test_name(node)
        if not isinstance(targets, list):
            raise RepositoryError(f"Для {node} ожидается список зависимостей")
        for target in targets:
            validate_test_name(target)
            if target not in data:
                message = f"Пакет {target} из {node} не описан в JSON"
                raise RepositoryError(message)
    return data


def load_test_repository(path: Path) -> StaticRepository:
    """Прочитать UTF-8 JSON и проверить его структуру до начала обхода."""
    try:
        if path.stat().st_size > MAX_TEST_REPOSITORY_BYTES:
            raise RepositoryError("Файл тестового репозитория слишком большой")
        with path.open(encoding="utf-8-sig") as stream:
            data = json.load(stream, object_pairs_hook=unique_object)
    except (OSError, UnicodeError, ValueError, RecursionError) as error:
        raise RepositoryError(f"Ошибка JSON {path}: {error}") from error
    return StaticRepository(validate_adjacency(data))


def create_repository(settings: Settings) -> NeighborSource:
    """Выбрать файловый или Maven-репозиторий согласно конфигурации."""
    if settings.test_mode:
        return load_test_repository(Path(settings.repository))
    return MavenRepository(settings.repository)
