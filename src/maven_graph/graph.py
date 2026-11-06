"""Построение графа рекурсивным поиском в ширину, включая циклы."""

from dataclasses import dataclass
from typing import Protocol

from maven_graph.coordinates import Coordinates
from maven_graph.errors import RepositoryError

RECURSIVE_BATCH = 64
EMPTY_BUDGET = 0
MAX_GRAPH_NODES = 10000
MAX_VISIT_STATES = 100000


@dataclass(frozen=True)
class Link:
    """Ребро к пакету и исключения, действующие ниже этого ребра."""

    target: str
    exclusions: frozenset[tuple[str, str]] = frozenset()


class NeighborSource(Protocol):
    """Минимальный интерфейс любого источника графа."""

    def neighbors(self, package: str) -> tuple[Link, ...]:
        """Вернуть исходящие рёбра пакета в порядке объявления."""
        ...


@dataclass(frozen=True)
class Visit:
    """Состояние BFS: пакет и накопленные ограничения конкретного пути."""

    package: str
    exclusions: frozenset[tuple[str, str]] = frozenset()


@dataclass(frozen=True)
class DependencyGraph:
    """Ориентированный граф; порядок вершин соответствует обнаружению BFS."""

    root: str
    adjacency: dict[str, tuple[str, ...]]

    @property
    def edge_count(self) -> int:
        """Посчитать уникальные рёбра, включая петли и обратные дуги."""
        return sum(len(targets) for targets in self.adjacency.values())


def is_excluded(target: str, exclusions: frozenset[tuple[str, str]]) -> bool:
    """Проверить Maven-исключения groupId/artifactId с поддержкой *."""
    if not exclusions:
        return False
    coordinates = Coordinates.parse(target)
    return any(
        group in {"*", coordinates.group}
        and artifact in {"*", coordinates.artifact}
        for group, artifact in exclusions
    )


class GraphBuilder:
    """Рекурсивный BFS по уровням с ограниченным размером стека Python."""

    def __init__(self, source: NeighborSource) -> None:
        """Подготовить состояние одного обхода и кеш соседей."""
        self.source = source
        self.adjacency: dict[str, dict[str, None]] = {}
        self.seen: set[Visit] = set()
        self.neighbor_cache: dict[str, tuple[Link, ...]] = {}

    def build(self, root: str) -> DependencyGraph:
        """Обойти достижимые вершины, сохранив все допустимые рёбра."""
        self.adjacency = {root: {}}
        initial = Visit(root)
        self.seen = {initial}
        self.neighbor_cache = {}
        frontier = [initial]
        while frontier:
            frontier = self.visit_levels(frontier, RECURSIVE_BATCH)
        adjacency = {
            node: tuple(targets) for node, targets in self.adjacency.items()
        }
        return DependencyGraph(root, adjacency)

    def visit_levels(self, frontier: list[Visit], budget: int) -> list[Visit]:
        """Обработать весь уровень перед рекурсивным переходом к следующему."""
        if not frontier or budget == EMPTY_BUDGET:
            return frontier
        following: list[Visit] = []
        for state in frontier:
            for link in self.neighbors(state.package):
                self.follow_link(state, link, following)
        return self.visit_levels(following, budget - 1)

    def neighbors(self, package: str) -> tuple[Link, ...]:
        """Запрашивать каждый пакет у источника не более одного раза."""
        if package not in self.neighbor_cache:
            self.neighbor_cache[package] = self.source.neighbors(package)
        return self.neighbor_cache[package]

    def follow_link(
        self, state: Visit, link: Link, following: list[Visit]
    ) -> None:
        """Сохранить ребро даже к посещённой вершине, но не зациклить обход."""
        if is_excluded(link.target, state.exclusions):
            return
        self.adjacency[state.package][link.target] = None
        self.adjacency.setdefault(link.target, {})
        exclusions = state.exclusions | link.exclusions
        target = Visit(link.target, exclusions)
        if target not in self.seen:
            self.seen.add(target)
            following.append(target)
        self.check_limits()

    def check_limits(self) -> None:
        """Остановить чрезмерно большой граф с явной диагностикой."""
        if len(self.adjacency) > MAX_GRAPH_NODES:
            raise RepositoryError(f"В графе больше {MAX_GRAPH_NODES} пакетов")
        if len(self.seen) > MAX_VISIT_STATES:
            message = f"В обходе больше {MAX_VISIT_STATES} состояний"
            raise RepositoryError(message)


def build_graph(root: str, source: NeighborSource) -> DependencyGraph:
    """Создать независимый рекурсивный BFS для одного корневого пакета."""
    return GraphBuilder(source).build(root)
