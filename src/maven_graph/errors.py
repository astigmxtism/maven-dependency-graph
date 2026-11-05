"""Ошибки, которые CLI показывает без трассировки стека."""


class GraphError(Exception):
    """Базовая ошибка приложения."""


class ConfigError(GraphError):
    """Некорректная конфигурация пользователя."""


class RepositoryError(GraphError):
    """Репозиторий недоступен или содержит некорректные данные."""
