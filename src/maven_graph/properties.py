"""Ленивая подстановка свойств Maven с контролем циклов."""

import re

from maven_graph.errors import RepositoryError

PROPERTY_PATTERN = re.compile(r"\$\{([^{}]+)\}")
MAX_PROPERTY_DEPTH = 64


class Properties:
    """Разрешать только используемые свойства, кешируя готовые значения."""

    def __init__(self, values: dict[str, str]) -> None:
        """Сохранить сырые значения и состояние текущей подстановки."""
        self.values = values
        self.resolved: dict[str, str] = {}
        self.active: set[str] = set()

    def expand(self, text: str) -> str:
        """Подставить все выражения ${name} в строке."""
        return PROPERTY_PATTERN.sub(self.replace, text)

    def replace(self, match: re.Match[str]) -> str:
        """Разрешить одно свойство, обнаруживая отсутствие и циклы."""
        name = match.group(1)
        if name in self.resolved:
            return self.resolved[name]
        if name in self.active:
            raise RepositoryError(f"Цикл свойств POM: {name}")
        if name not in self.values:
            raise RepositoryError(f"Неизвестное свойство POM: ${{{name}}}")
        if len(self.active) >= MAX_PROPERTY_DEPTH:
            raise RepositoryError("Слишком глубокая вложенность свойств POM")
        self.active.add(name)
        try:
            value = self.expand(self.values[name])
            self.resolved[name] = value
            return value
        finally:
            self.active.remove(name)
