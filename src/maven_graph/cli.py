"""Интерфейс командной строки анализа прямых и обратных зависимостей."""

import argparse
import sys
from pathlib import Path

from maven_graph.ascii_tree import ascii_tree
from maven_graph.config import DEFAULT_CONFIG, Settings, load_config
from maven_graph.errors import GraphError
from maven_graph.graph import DependencyGraph
from maven_graph.operations import analyze_graph
from maven_graph.repositories import create_repository
from maven_graph.visualization import export_graph, open_image

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


def present_graph(graph: DependencyGraph, settings: Settings) -> None:
    """Вывести сводку, ASCII-дерево и пути файлов; показать SVG по настройке."""
    direction = "Обратный граф" if settings.reverse.enabled else "Граф"
    print(f"{direction}: {graph.root}")
    print(f"Вершин: {len(graph.adjacency)}; рёбер: {graph.edge_count}")
    if settings.ascii_tree:
        print(ascii_tree(graph))
    files = export_graph(graph, settings.display, settings.reverse.enabled)
    print(f"PlantUML: {files.source}")
    if files.image:
        print(f"Изображение: {files.image}")
        if settings.display.open_image:
            open_image(files.image)


def main(argv: list[str] | None = None) -> int:
    """Построить граф или показать понятную ошибку."""
    args = make_parser().parse_args(argv)
    try:
        settings = load_config(args.config)
        repository = create_repository(settings)
        graph = analyze_graph(settings, repository)
        present_graph(graph, settings)
    except GraphError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_SUCCESS
