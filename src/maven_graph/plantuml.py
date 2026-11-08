"""Текст PlantUML и его стандартное URL-кодирование без внешних библиотек."""

import base64
import zlib

from maven_graph.graph import DependencyGraph

BASE64_ALPHABET = (
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
)
PLANTUML_ALPHABET = (
    b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"
)
ENCODING_TABLE = bytes.maketrans(BASE64_ALPHABET, PLANTUML_ALPHABET)


def escape_label(value: str) -> str:
    """Экранировать кавычки, слеши и переводы строк в подписи вершины."""
    return (
        value.replace("\\", "\\\\").replace('"', '\\"')
        .replace("\r", "").replace("\n", "\\n")
    )


def to_plantuml(graph: DependencyGraph, reverse: bool = False) -> str:
    """Создать детерминированную диаграмму со всеми вершинами и рёбрами."""
    aliases = {node: f"p{index}" for index, node in enumerate(graph.adjacency)}
    title = "Reverse dependencies" if reverse else "Maven dependency graph"
    lines = [
        "@startuml", "left to right direction", "skinparam shadowing false",
        f"title {title}",
    ]
    for node, alias in aliases.items():
        color = " #E8F4FD" if node == graph.root else ""
        lines.append(f'rectangle "{escape_label(node)}" as {alias}{color}')
    for node, targets in graph.adjacency.items():
        for target in targets:
            lines.append(f"{aliases[node]} --> {aliases[target]}")
    if reverse:
        lines.append("caption X -> Y means: Y depends on X")
    lines.append("@enduml")
    return "\n".join(lines) + "\n"


def encode_plantuml(source: str) -> str:
    """Сжать UTF-8 raw-deflate и применить алфавит PlantUML base64."""
    compressor = zlib.compressobj(wbits=-zlib.MAX_WBITS)
    data = compressor.compress(source.encode("utf-8")) + compressor.flush()
    encoded = base64.b64encode(data).translate(ENCODING_TABLE)
    return encoded.replace(b"=", b"0").decode("ascii")
