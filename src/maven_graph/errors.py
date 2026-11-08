"""Ошибки, которые CLI показывает без трассировки стека."""


class GraphError(Exception):
    """Базовая ошибка приложения."""


class ConfigError(GraphError):
    """Некорректная конфигурация пользователя."""


class RepositoryError(GraphError):
    """Репозиторий недоступен или содержит некорректные данные."""


class VisualizationError(GraphError):
    """Не удалось сохранить, отрисовать или открыть диаграмму."""
