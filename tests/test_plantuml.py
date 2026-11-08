"""Семантические проверки PlantUML и URL-кодирования без GUI."""

import base64
import unittest
import zlib

from maven_graph.graph import DependencyGraph
from maven_graph.plantuml import encode_plantuml, to_plantuml


class PlantUmlTests(unittest.TestCase):
    """Проверять вершины, рёбра, экранирование и фактическую распаковку."""

    def test_all_nodes_edges_and_cycle_are_preserved(self) -> None:
        """В диаграмме присутствуют все дуги, включая петлю и общую вершину."""
        graph = DependencyGraph("A", {
            "A": ("A", "B", "C"), "B": ("C",), "C": (),
        })
        source = to_plantuml(graph)
        edges = {line for line in source.splitlines() if " --> " in line}
        expected = {"p0 --> p0", "p0 --> p1", "p0 --> p2", "p1 --> p2"}
        self.assertEqual(edges, expected)
        self.assertEqual(source.count("rectangle "), 3)
        self.assertTrue(source.endswith("@enduml\n"))

    def test_isolated_node_and_reverse_caption(self) -> None:
        """Пакет без рёбер остаётся на диаграмме; направление поясняется."""
        source = to_plantuml(DependencyGraph("A", {"A": ()}), reverse=True)
        self.assertIn('rectangle "A" as p0', source)
        self.assertIn("Y depends on X", source)
        self.assertNotIn(" --> ", source)

    def test_labels_cannot_add_diagram_commands(self) -> None:
        """Кавычки и перевод строки остаются частью подписи."""
        name = 'A"\\\n@enduml'
        source = to_plantuml(DependencyGraph(name, {name: ()}))
        self.assertEqual(source.count("\n@enduml"), 1)
        self.assertIn('A\\"\\\\\\n@enduml', source)

    def test_encoded_text_can_be_decoded_as_raw_deflate(self) -> None:
        """Кодирование сохраняет UTF-8 и все варианты base64-padding."""
        plantuml = (
            "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"
        )
        standard = (
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        )
        table = str.maketrans(plantuml, standard)
        for source in ("A", "Привет", "@startuml\nA --> B\n@enduml\n"):
            with self.subTest(source=source):
                encoded = encode_plantuml(source)
                raw = base64.b64decode(encoded.translate(table))
                restored = zlib.decompress(raw, wbits=-zlib.MAX_WBITS)
                self.assertEqual(restored.decode("utf-8"), source)
