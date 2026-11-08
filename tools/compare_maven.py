"""Независимо сравнить графы приложения и штатный mvn dependency:tree."""

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TREE_LINE = re.compile(r"^((?:\|  |   )*)(?:\+- |\\- )(\S+)")
INDENT_WIDTH = 3
COORDINATE_PART_COUNTS = {5, 6}
EXAMPLES = (
    "junit:junit:4.13.2",
    "org.slf4j:slf4j-simple:2.0.16",
    "org.apache.httpcomponents:httpclient:4.5.14",
)


def parse_tree(text: str) -> dict[str, tuple[str, ...]]:
    """Извлечь GAV и дуги из ASCII Maven, исключая временного consumer."""
    adjacency: dict[str, list[str]] = {}
    stack: list[str] = []
    for line in text.splitlines()[1:]:
        match = TREE_LINE.match(line)
        if not match:
            raise ValueError(f"Неожиданная строка Maven: {line}")
        prefix, value = match.groups()
        parts = value.split(":")
        if len(parts) not in COORDINATE_PART_COUNTS:
            raise ValueError(f"Неожиданные координаты Maven: {value}")
        node = ":".join((parts[0], parts[1], parts[-2]))
        depth = len(prefix) // INDENT_WIDTH
        if depth > len(stack):
            raise ValueError("Нарушен порядок уровней Maven-дерева")
        stack = stack[:depth]
        adjacency.setdefault(node, [])
        if stack:
            adjacency[stack[-1]].append(node)
        stack.append(node)
    if not adjacency:
        raise ValueError("Maven не вернул дерево выбранного пакета")
    return {node: tuple(targets) for node, targets in adjacency.items()}


def edges(adjacency: dict[str, tuple[str, ...]]) -> set[tuple[str, str]]:
    """Представить рёбра независимо от порядка сериализации."""
    return {
        (node, target)
        for node, targets in adjacency.items()
        for target in targets
    }


def compare_package(package: str, maven: Path, folder: Path) -> bool:
    """Сравнить реальные вершины и рёбра двух независимых реализаций."""
    from maven_graph.graph import build_graph
    from maven_graph.maven import MavenRepository
    from tools.maven_reference import CENTRAL, dependency_tree

    working = folder / package.replace(":", "_")
    tree = dependency_tree(maven, package, working, folder / "cache")
    reference = parse_tree(tree)
    actual = build_graph(package, MavenRepository(CENTRAL)).adjacency
    actual_edges = edges(actual)
    reference_edges = edges(reference)
    same_nodes = set(actual) == set(reference)
    same_edges = actual_edges == reference_edges
    print(f"\n{package}\n{tree.rstrip()}")
    print(f"Приложение: {len(actual)} вершин, {len(actual_edges)} рёбер")
    print(f"Maven: {len(reference)} вершин, {len(reference_edges)} рёбер")
    print(f"Совпали вершины: {same_nodes}; совпали рёбра: {same_edges}")
    if not same_nodes or not same_edges:
        print(f"Только в приложении: {sorted(actual_edges - reference_edges)}")
        print(f"Только в Maven: {sorted(reference_edges - actual_edges)}")
    return same_nodes and same_edges


def main() -> int:
    """Создать изолированную среду сравнения и удалить её после завершения."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap", action="store_true")
    parser.add_argument("--temp-root", type=Path, default=None)
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "src"))
    from maven_graph.errors import GraphError
    from tools.maven_reference import execute_maven, locate_maven

    try:
        with tempfile.TemporaryDirectory(dir=args.temp_root) as temporary:
            folder = Path(temporary)
            maven = locate_maven(folder, args.bootstrap)
            print(execute_maven(maven, ["--version"], folder).rstrip())
            results = [
                compare_package(item, maven, folder) for item in EXAMPLES
            ]
    except (
        OSError, RuntimeError, ValueError,
        subprocess.SubprocessError, GraphError,
    ) as error:
        print(f"Ошибка сравнения: {error}", file=sys.stderr)
        return 1
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
