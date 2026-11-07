"""Прямые и обратные зависимости на основе одного рекурсивного BFS."""

from maven_graph.config import Settings
from maven_graph.graph import DependencyGraph, NeighborSource, build_graph
from maven_graph.repositories import StaticRepository


def invert_adjacency(
    adjacency: dict[str, tuple[str, ...]],
) -> dict[str, list[str]]:
    """Развернуть все дуги, сохранив изолированные вершины и петли."""
    inverted: dict[str, list[str]] = {node: [] for node in adjacency}
    for node, targets in adjacency.items():
        for target in targets:
            inverted.setdefault(target, []).append(node)
    return inverted


def build_reverse_graph(
    target: str, adjacency: dict[str, tuple[str, ...]]
) -> DependencyGraph:
    """Выполнить тот же рекурсивный BFS по транспонированному графу."""
    repository = StaticRepository(invert_adjacency(adjacency))
    return build_graph(target, repository)


def analyze_graph(
    settings: Settings, source: NeighborSource
) -> DependencyGraph:
    """Выбрать направление и корректную область поиска зависимостей."""
    if not settings.reverse.enabled:
        return build_graph(settings.package, source)
    target = settings.reverse.target or settings.package
    if isinstance(source, StaticRepository):
        adjacency = source.adjacency
    else:
        adjacency = build_graph(settings.package, source).adjacency
    return build_reverse_graph(target, adjacency)


def reverse_dependents(graph: DependencyGraph) -> tuple[str, ...]:
    """Вернуть все обратные зависимости в порядке BFS, исключая сам корень."""
    return tuple(node for node in graph.adjacency if node != graph.root)
