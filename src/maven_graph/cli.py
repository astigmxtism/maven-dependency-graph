"""Интерфейс командной строки этапа получения прямых зависимостей."""

import argparse
import sys
from pathlib import Path

from maven_graph.config import DEFAULT_CONFIG, load_config
from maven_graph.errors import GraphError
from maven_graph.maven import MavenRepository

EXIT_SUCCESS = 0
EXIT_ERROR = 2


def make_parser() -> argparse.ArgumentParser:
    """Описать CLI; параметры анализа остаются в INI."""
    parser = argparse.ArgumentParser(
        description="Визуализатор зависимостей Maven, вариант №2"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="путь к INI-файлу (по умолчанию config.ini проекта)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Вывести прямые зависимости или понятную ошибку."""
    args = make_parser().parse_args(argv)
    try:
        settings = load_config(args.config)
        if settings.test_mode:
            raise GraphError("Файловый репозиторий будет доступен на этапе 3")
        repository = MavenRepository(settings.repository)
        dependencies = repository.direct_dependencies(settings.package)
        print(f"Прямые зависимости {settings.package}:")
        for dependency in dependencies:
            optional = ", optional" if dependency.optional else ""
            print(f"{dependency.coordinates} [{dependency.scope}{optional}]")
        if not dependencies:
            print("(нет зависимостей)")
    except GraphError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_SUCCESS
