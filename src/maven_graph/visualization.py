"""Сохранение PlantUML, получение SVG и открытие изображения пользователем."""

import re
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from maven_graph.config import DisplaySettings
from maven_graph.errors import RepositoryError, VisualizationError
from maven_graph.graph import DependencyGraph
from maven_graph.http import fetch_bytes
from maven_graph.plantuml import encode_plantuml, to_plantuml


@dataclass(frozen=True)
class VisualizationFiles:
    """Пути успешно созданных результатов визуализации."""

    source: Path
    image: Path | None = None


def render_svg(source: str, server: str) -> bytes:
    """Получить SVG от PlantUML-сервера и проверить формат ответа как данные."""
    url = f"{server.rstrip('/')}/svg/{encode_plantuml(source)}"
    try:
        data = fetch_bytes(url)
    except RepositoryError as error:
        raise VisualizationError(f"PlantUML: {error}") from error
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError as error:
        raise VisualizationError("PlantUML вернул некорректный SVG") from error
    if root.tag.rsplit("}", 1)[-1] != "svg":
        raise VisualizationError("PlantUML вернул ответ другого формата")
    return data


def output_stem(package: str, reverse: bool) -> str:
    """Составить переносимое имя результата из координат пакета."""
    name = re.sub(r"[^A-Za-z0-9_.-]", "_", package).strip("._") or "graph"
    return name + ("-reverse" if reverse else "")


def export_graph(
    graph: DependencyGraph, settings: DisplaySettings, reverse: bool = False
) -> VisualizationFiles:
    """Сначала сохранить исходный PlantUML, затем получить SVG при включении."""
    stem = output_stem(graph.root, reverse)
    source_path = settings.output_dir / f"{stem}.puml"
    source = to_plantuml(graph, reverse)
    try:
        settings.output_dir.mkdir(parents=True, exist_ok=True)
        source_path.write_text(source, encoding="utf-8")
        if not settings.render:
            return VisualizationFiles(source_path)
        image_path = settings.output_dir / f"{stem}.svg"
        image_path.write_bytes(render_svg(source, settings.plantuml_url))
    except OSError as error:
        message = f"Не удалось сохранить диаграмму: {error}"
        raise VisualizationError(message) from error
    return VisualizationFiles(source_path, image_path)


def open_image(path: Path) -> None:
    """Открыть сохранённое SVG в системном просмотрщике через file URI."""
    try:
        opened = webbrowser.open(path.resolve().as_uri(), new=2)
    except (OSError, webbrowser.Error) as error:
        message = f"Не удалось открыть изображение: {path}"
        raise VisualizationError(message) from error
    if not opened:
        raise VisualizationError(f"Просмотрщик недоступен; файл: {path}")
