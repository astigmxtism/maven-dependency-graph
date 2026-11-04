"""Проверка и разбор координат Maven без сторонних библиотек."""

import re
from dataclasses import dataclass

from maven_graph.errors import ConfigError

COORDINATE_PARTS = 3
GROUP_PATTERN = r"[A-Za-z0-9_]+(?:[.-][A-Za-z0-9_]+)*"
PART_PATTERN = r"[A-Za-z0-9_][A-Za-z0-9_.+-]*"
TEST_PACKAGE_PATTERN = r"[A-Z]+"


@dataclass(frozen=True)
class Coordinates:
    """Однозначный адрес пакета: группа, артефакт и версия."""

    group: str
    artifact: str
    version: str

    @classmethod
    def parse(cls, value: str) -> "Coordinates":
        """Проверить три части координат и запретить пути/диапазоны."""
        parts = value.split(":")
        if len(parts) != COORDINATE_PARTS:
            raise ConfigError(
                "package: ожидаются координаты groupId:artifactId:version"
            )
        group, artifact, version = parts
        valid = (
            re.fullmatch(GROUP_PATTERN, group)
            and re.fullmatch(PART_PATTERN, artifact)
            and re.fullmatch(PART_PATTERN, version)
        )
        if not valid:
            raise ConfigError(f"package: неверные координаты {value!r}")
        if version in {"LATEST", "RELEASE"}:
            raise ConfigError("package: требуется конкретная версия")
        return cls(group, artifact, version)

    def __str__(self) -> str:
        """Вернуть каноническое представление координат."""
        return f"{self.group}:{self.artifact}:{self.version}"

    @property
    def pom_path(self) -> str:
        """Вернуть относительный адрес POM в Maven-репозитории."""
        group_path = self.group.replace(".", "/")
        filename = f"{self.artifact}-{self.version}.pom"
        return f"{group_path}/{self.artifact}/{self.version}/{filename}"


def validate_package(package: str, test_mode: bool) -> None:
    """Проверить имя с учётом выбранного типа репозитория."""
    if not test_mode:
        Coordinates.parse(package)
    elif not re.fullmatch(TEST_PACKAGE_PATTERN, package):
        raise ConfigError("package: нужны большие латинские буквы, например A")
