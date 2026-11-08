"""Запуск штатного Maven исключительно для независимого сравнения."""

import hashlib
import io
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from urllib.request import urlopen

MAVEN_VERSION = "3.9.9"
PLUGIN_VERSION = "3.8.1"
CENTRAL = "https://repo.maven.apache.org/maven2"
ARCHIVE_URL = (
    f"{CENTRAL}/org/apache/maven/apache-maven/{MAVEN_VERSION}/"
    f"apache-maven-{MAVEN_VERSION}-bin.zip"
)
DOWNLOAD_TIMEOUT = 60
COMMAND_TIMEOUT = 300
MAX_DOWNLOAD_BYTES = 16 * 1024 * 1024
SUCCESS = 0


def download(url: str) -> bytes:
    """Загрузить дистрибутив для сравнения, не используя код приложения."""
    with urlopen(url, timeout=DOWNLOAD_TIMEOUT) as response:
        data = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise RuntimeError("Слишком большой дистрибутив Maven")
    return data


def locate_maven(folder: Path, bootstrap: bool) -> Path:
    """Использовать Maven из PATH или временный проверенный дистрибутив."""
    installed = shutil.which("mvn")
    if installed:
        return Path(installed)
    if not bootstrap:
        raise RuntimeError("Maven не найден; укажите --bootstrap или PATH")
    archive = download(ARCHIVE_URL)
    expected = download(ARCHIVE_URL + ".sha512").decode().split()[0]
    if hashlib.sha512(archive).hexdigest() != expected:
        raise RuntimeError("Не совпала SHA-512 дистрибутива Maven")
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        for member in bundle.infolist():
            target = (folder / member.filename).resolve()
            if not target.is_relative_to(folder.resolve()):
                raise RuntimeError("Недопустимый путь в дистрибутиве Maven")
        bundle.extractall(folder)
    name = "mvn.cmd" if os.name == "nt" else "mvn"
    return folder / f"apache-maven-{MAVEN_VERSION}" / "bin" / name


def java_environment() -> dict[str, str]:
    """Определить JAVA_HOME из установленной Java при отсутствии переменной."""
    environment = dict(os.environ)
    if environment.get("JAVA_HOME"):
        return environment
    result = subprocess.run(
        ["java", "-XshowSettings:properties", "-version"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=True, timeout=COMMAND_TIMEOUT,
    )
    match = re.search(r"^\s*java.home = (.+)$", result.stderr, re.MULTILINE)
    if match:
        environment["JAVA_HOME"] = match.group(1).strip()
    return environment


def execute_maven(maven: Path, arguments: list[str], folder: Path) -> str:
    """Выполнить Maven без компиляции и вернуть диагностический вывод."""
    command = [str(maven)] if os.name == "nt" else ["sh", str(maven)]
    result = subprocess.run(
        command + arguments, cwd=folder, env=java_environment(),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=COMMAND_TIMEOUT,
    )
    if result.returncode != SUCCESS:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout


def consumer_pom(package: str) -> str:
    """Составить отдельный POM потребителя ровно одного исследуемого пакета."""
    group, artifact, version = package.split(":")
    return (
        '<project xmlns="http://maven.apache.org/POM/4.0.0">\n'
        "  <modelVersion>4.0.0</modelVersion>\n"
        "  <groupId>comparison</groupId><artifactId>consumer</artifactId>\n"
        "  <version>1</version>\n  <dependencies><dependency>\n"
        f"    <groupId>{group}</groupId><artifactId>{artifact}</artifactId>\n"
        f"    <version>{version}</version>\n"
        "  </dependency></dependencies>\n</project>\n"
    )


def dependency_tree(
    maven: Path, package: str, folder: Path, cache: Path
) -> str:
    """Получить штатное текстовое runtime-дерево во временном Maven-проекте."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "pom.xml").write_text(consumer_pom(package), encoding="utf-8")
    output = folder / "tree.txt"
    plugin = "org.apache.maven.plugins:maven-dependency-plugin:"
    plugin += PLUGIN_VERSION
    arguments = [
        "-q", "-B", "-ntp", f"-Dmaven.repo.local={cache}", f"{plugin}:tree",
        "-Dscope=runtime", "-DoutputType=text", f"-DoutputFile={output}",
    ]
    execute_maven(maven, arguments, folder)
    return output.read_text(encoding="utf-8")
