"""Минимальный интерфейс командной строки первого этапа."""

import argparse
import sys
from dataclasses import asdict
from pathlib import Path

from maven_graph.config import DEFAULT_CONFIG, load_config
from maven_graph.errors import GraphError

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
    """Вывести настройки или понятную ошибку с ненулевым кодом."""
    args = make_parser().parse_args(argv)
    try:
        settings = load_config(args.config)
        for key, value in asdict(settings).items():
            text = str(value).lower() if isinstance(value, bool) else value
            print(f"{key}={text}")
    except GraphError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_SUCCESS
