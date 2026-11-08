"""ASCII-представление графа без зацикливания и повторного раскрытия узлов."""

from dataclasses import dataclass, replace

from maven_graph.graph import DependencyGraph


@dataclass(frozen=True)
class TreeEntry:
    """Событие итеративного раскрытия или закрытия ветви дерева."""

    node: str
    prefix: str = ""
    last: bool = True
    root: bool = False
    closing: bool = False


class AsciiTree:
    """Развёртка графа в дерево с отдельными отметками циклов и повторов."""

    def __init__(self, graph: DependencyGraph) -> None:
        """Подготовить стек событий и множества раскрытых/активных вершин."""
        self.graph = graph
        self.stack = [TreeEntry(graph.root, root=True)]
        self.lines: list[str] = []
        self.active: set[str] = set()
        self.expanded: set[str] = set()

    def render(self) -> str:
        """Построить дерево без ограничения глубиной стека Python."""
        while self.stack:
            entry = self.stack.pop()
            if entry.closing:
                self.active.remove(entry.node)
            else:
                self.visit(entry)
        return "\n".join(self.lines)

    def marker(self, node: str) -> str:
        """Отличить цикл текущего пути от общей зависимости другого пути."""
        if node in self.active:
            return " [cycle]"
        if node in self.expanded:
            return " [shared]"
        return ""

    def visit(self, entry: TreeEntry) -> None:
        """Вывести вершину и раскрыть её только при первом посещении."""
        connector = "\\-- " if entry.last else "+-- "
        if entry.root:
            connector = ""
        marker = self.marker(entry.node)
        self.lines.append(f"{entry.prefix}{connector}{entry.node}{marker}")
        if marker:
            return
        self.active.add(entry.node)
        self.expanded.add(entry.node)
        self.stack.append(replace(entry, closing=True))
        self.push_children(entry)

    def push_children(self, entry: TreeEntry) -> None:
        """Положить детей в обратном порядке для стабильного вывода."""
        prefix = entry.prefix
        if not entry.root:
            prefix += "    " if entry.last else "|   "
        children = self.graph.adjacency[entry.node]
        for child in reversed(children):
            self.stack.append(TreeEntry(child, prefix, child == children[-1]))


def ascii_tree(graph: DependencyGraph) -> str:
    """Получить ASCII-дерево с отметками [cycle] и [shared]."""
    return AsciiTree(graph).render()
