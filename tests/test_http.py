"""Ошибки транспорта проверяются без подключения к внешней сети."""

import io
import unittest
from urllib.error import HTTPError, URLError
from unittest.mock import patch

from maven_graph.errors import RepositoryError
from maven_graph.http import fetch_bytes

URL = "https://repository.example/example/app/1/app-1.pom"


class HttpTests(unittest.TestCase):
    """Проверки таймаута, HTTP, URL и ограничения размера ответа."""

    def test_success(self) -> None:
        """URL передаётся urllib, байты ответа возвращаются без изменений."""
        with patch("maven_graph.http.urlopen", return_value=io.BytesIO(b"POM")):
            self.assertEqual(fetch_bytes(URL), b"POM")

    def test_network_failures(self) -> None:
        """404, таймаут и ошибка DNS преобразуются в ошибку репозитория."""
        errors = (
            HTTPError(URL, 404, "Not Found", {}, None),
            URLError("DNS failure"), TimeoutError("timeout"),
        )
        for error in errors:
            with self.subTest(error=error):
                with patch("maven_graph.http.urlopen", side_effect=error):
                    with self.assertRaisesRegex(RepositoryError, "https://"):
                        fetch_bytes(URL)

    def test_response_size_limit(self) -> None:
        """Слишком большой ответ не передаётся XML-парсеру."""
        with patch("maven_graph.http.MAX_RESPONSE_BYTES", 3):
            response = io.BytesIO(b"1234")
            with patch("maven_graph.http.urlopen", return_value=response):
                with self.assertRaisesRegex(RepositoryError, "больше"):
                    fetch_bytes(URL)
