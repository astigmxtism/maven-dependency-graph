"""Интерфейс командной строки этапа построения графа зависимостей."""

import argparse
import sys
from pathlib import Path

from maven_graph.config import DEFAULT_CONFIG, load_config
from maven_graph.errors import GraphError
from maven_graph.graph import DependencyGraph, build_graph
from maven_graph.repositories import create_repository

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


def print_graph(graph: DependencyGraph) -> None:
    """Показать все вершины и рёбра в порядке BFS."""
    print("Порядок BFS: " + ", ".join(graph.adjacency))
    for node, targets in graph.adjacency.items():
        print(f"{node} -> {', '.join(targets) or '(нет зависимостей)'}")
    print(f"Вершин: {len(graph.adjacency)}; рёбер: {graph.edge_count}")


def main(argv: list[str] | None = None) -> int:
    """Построить граф или показать понятную ошибку."""
    args = make_parser().parse_args(argv)
    try:
        settings = load_config(args.config)
        repository = create_repository(settings)
        graph = build_graph(settings.package, repository)
        print_graph(graph)
    except GraphError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_SUCCESS
