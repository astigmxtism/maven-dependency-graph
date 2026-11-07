"""Чтение строгой INI-конфигурации и проверка каждого параметра."""

import configparser
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from maven_graph.coordinates import validate_package
from maven_graph.errors import ConfigError

SECTION = "settings"
REQUIRED_KEYS = {"package", "repository", "test_mode", "ascii_tree"}
OPTIONAL_KEYS = {"reverse", "reverse_target"}
DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config.ini"


@dataclass(frozen=True)
class ReverseSettings:
    """Параметры обратного обхода в пределах известного графа."""

    enabled: bool = False
    target: str = ""


@dataclass(frozen=True)
class Settings:
    """Проверенные пользовательские параметры приложения."""

    package: str
    repository: str
    test_mode: bool
    ascii_tree: bool
    reverse: ReverseSettings = field(default_factory=ReverseSettings)


def read_ini(path: Path) -> configparser.ConfigParser:
    """Прочитать UTF-8 INI и преобразовать ошибки ввода в ConfigError."""
    parser = configparser.ConfigParser(
        interpolation=None, empty_lines_in_values=False
    )
    try:
        with path.open(encoding="utf-8-sig") as stream:
            parser.read_file(stream)
    except (OSError, UnicodeError, configparser.Error) as error:
        raise ConfigError(f"INI {path}: {error}") from error
    return parser


def validate_schema(parser: configparser.ConfigParser) -> None:
    """Запретить пропуски, опечатки и неоговорённые секции."""
    if parser.sections() != [SECTION] or parser.defaults():
        raise ConfigError("INI: допустима только секция [settings]")
    keys = set(parser[SECTION])
    missing = REQUIRED_KEYS - keys
    unknown = keys - REQUIRED_KEYS - OPTIONAL_KEYS
    if missing:
        message = "INI: отсутствуют ключи " + ", ".join(sorted(missing))
        raise ConfigError(message)
    if unknown:
        message = "INI: неизвестные ключи " + ", ".join(sorted(unknown))
        raise ConfigError(message)


def read_boolean(
    section: configparser.SectionProxy, key: str, default: bool = False
) -> bool:
    """Получить логический параметр с адресным сообщением об ошибке."""
    try:
        return section.getboolean(key, fallback=default)
    except ValueError as error:
        raise ConfigError(f"{key}: ожидается true или false") from error


def validate_url(value: str, key: str = "repository") -> str:
    """Принять абсолютный HTTP(S)-адрес без пароля, query и fragment."""
    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme in {"http", "https"}
            and parsed.hostname
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
            and not any(char.isspace() for char in value)
        )
        parsed.port
    except ValueError as error:
        raise ConfigError(f"{key}: некорректный URL") from error
    if not valid:
        raise ConfigError(f"{key}: ожидается абсолютный HTTP(S)-адрес")
    return value.rstrip("/")


def validate_repository(value: str, test_mode: bool, base: Path) -> str:
    """Проверить URL или доступный файл относительно INI."""
    if not value:
        raise ConfigError("repository: значение не должно быть пустым")
    if not test_mode:
        return validate_url(value)
    path = (base / value).resolve()
    try:
        with path.open("rb"):
            pass
    except OSError as error:
        raise ConfigError(f"repository: файл недоступен: {path}") from error
    return str(path)


def load_config(path: Path) -> Settings:
    """Загрузить конфигурацию и проверить все обязательные параметры."""
    parser = read_ini(path)
    validate_schema(parser)
    section = parser[SECTION]
    test_mode = read_boolean(section, "test_mode")
    ascii_tree = read_boolean(section, "ascii_tree")
    package = section["package"].strip()
    validate_package(package, test_mode)
    repository = validate_repository(
        section["repository"].strip(), test_mode, path.resolve().parent
    )
    reverse = read_reverse(section, test_mode)
    return Settings(package, repository, test_mode, ascii_tree, reverse)


def read_reverse(
    section: configparser.SectionProxy, test_mode: bool
) -> ReverseSettings:
    """Проверить режим и необязательную цель обратного поиска."""
    enabled = read_boolean(section, "reverse")
    target = section.get("reverse_target", "").strip()
    if target and not enabled:
        raise ConfigError("reverse_target: требуется reverse=true")
    if target:
        try:
            validate_package(target, test_mode)
        except ConfigError as error:
            raise ConfigError(f"reverse_target: {error}") from error
    return ReverseSettings(enabled, target)
