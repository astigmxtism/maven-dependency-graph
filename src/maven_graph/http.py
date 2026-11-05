"""Загрузка метаданных по HTTP(S) средствами стандартной библиотеки."""

from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from maven_graph.errors import RepositoryError

NETWORK_TIMEOUT = 30
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
USER_AGENT = "maven-dependency-graph/1.0 (Python urllib)"


def fetch_bytes(url: str) -> bytes:
    """Загрузить ограниченный по размеру ответ с таймаутом."""
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=NETWORK_TIMEOUT) as response:
            data = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as error:
        raise RepositoryError(f"HTTP {error.code}: {url}") from error
    except (URLError, OSError, HTTPException, ValueError) as error:
        raise RepositoryError(f"Не удалось загрузить {url}: {error}") from error
    if len(data) > MAX_RESPONSE_BYTES:
        raise RepositoryError(f"Ответ больше {MAX_RESPONSE_BYTES} байт: {url}")
    return data
