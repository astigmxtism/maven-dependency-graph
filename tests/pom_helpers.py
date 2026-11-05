"""Миниатюрный Maven-репозиторий в памяти для независимых тестов."""

from maven_graph.coordinates import Coordinates
from maven_graph.maven import MavenRepository

BASE_URL = "https://repository.example/maven2"


def make_pom(body: str = "", artifact: str = "app", version: str = "1") -> str:
    """Создать небольшой namespaced POM с заданным содержимым."""
    return (
        '<project xmlns="http://maven.apache.org/POM/4.0.0">'
        "<modelVersion>4.0.0</modelVersion><groupId>example</groupId>"
        f"<artifactId>{artifact}</artifactId><version>{version}</version>"
        f"{body}</project>"
    )


def dependency_xml(
    artifact: str = "lib", version: str = "1", extra: str = ""
) -> str:
    """Создать XML объявления зависимости для отдельных сценариев."""
    version_tag = f"<version>{version}</version>" if version else ""
    return (
        "<dependency><groupId>example</groupId>"
        f"<artifactId>{artifact}</artifactId>{version_tag}{extra}</dependency>"
    )


class MemoryRepository(MavenRepository):
    """Подставлять POM вместо сети, сохраняя реальные URL запросов."""

    def __init__(self, poms: dict[str, str]) -> None:
        """Индексировать фикстуры по Maven-путям."""
        self.poms = {
            f"{BASE_URL}/{Coordinates.parse(key).pom_path}": value.encode()
            for key, value in poms.items()
        }
        self.requests: list[str] = []
        super().__init__(BASE_URL, self.fetch)

    def fetch(self, url: str) -> bytes:
        """Вернуть XML фикстуры по адресу, вычисленному приложением."""
        self.requests.append(url)
        return self.poms[url]
