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
VISUALIZATION_SECTION = "visualization"
VISUALIZATION_KEYS = {"output_dir", "plantuml_url", "render", "open_image"}
DEFAULT_OUTPUT = DEFAULT_CONFIG.parent / "output"
DEFAULT_PLANTUML_URL = "https://www.plantuml.com/plantuml"


@dataclass(frozen=True)
class ReverseSettings:
    """Параметры обратного обхода в пределах известного графа."""

    enabled: bool = False
    target: str = ""


@dataclass(frozen=True)
class DisplaySettings:
    """Параметры сохранения PlantUML, получения SVG и показа изображения."""

    output_dir: Path = DEFAULT_OUTPUT
    plantuml_url: str = DEFAULT_PLANTUML_URL
    render: bool = True
    open_image: bool = True


@dataclass(frozen=True)
class Settings:
    """Проверенные пользовательские параметры приложения."""

    package: str
    repository: str
    test_mode: bool
    ascii_tree: bool
    reverse: ReverseSettings = field(default_factory=ReverseSettings)
    display: DisplaySettings = field(default_factory=DisplaySettings)


def read_ini(path: Path) -> configparser.ConfigParser:
    """Прочитать UTF-8 INI и преобразовать ошибки ввода в ConfigError."""
    parser = configparser.ConfigParser(
        interpolation=None, empty_lines_in_values=False
    )
    try:
        with path.open(encoding="utf-8-sig") as stream:
            parser.read_file(stream)
    except (OSError, UnicodeError, ValueError, configparser.Error) as error:
        raise ConfigError(f"INI {path}: {error}") from error
    return parser


def validate_schema(parser: configparser.ConfigParser) -> None:
    """Запретить пропуски, опечатки и неоговорённые секции."""
    allowed = {SECTION, VISUALIZATION_SECTION}
    if SECTION not in parser or parser.defaults():
        raise ConfigError("INI: нужна секция [settings], DEFAULT недопустим")
    if set(parser.sections()) - allowed:
        raise ConfigError("INI: неизвестная секция")
    validate_keys(parser[SECTION], REQUIRED_KEYS, OPTIONAL_KEYS)
    if VISUALIZATION_SECTION in parser:
        validate_keys(parser[VISUALIZATION_SECTION], set(), VISUALIZATION_KEYS)


def validate_keys(
    section: configparser.SectionProxy, required: set[str], optional: set[str]
) -> None:
    """Проверить набор ключей одной секции."""
    keys = set(section)
    missing = required - keys
    unknown = keys - required - optional
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
            and parsed.username is None
            and parsed.password is None
            and not url_has_forbidden_characters(value)
        )
        parsed.port
    except ValueError as error:
        raise ConfigError(f"{key}: некорректный URL") from error
    if not valid:
        raise ConfigError(f"{key}: ожидается абсолютный HTTP(S)-адрес")
    return value.rstrip("/")


def url_has_forbidden_characters(value: str) -> bool:
    """Не допустить query, fragment, пробелы и неоднозначные разделители."""
    forbidden = {"?", "#", "\\", "\0"}
    return any(char.isspace() or char in forbidden for char in value)


def validate_repository(value: str, test_mode: bool, base: Path) -> str:
    """Проверить URL или доступный файл относительно INI."""
    if not value:
        raise ConfigError("repository: значение не должно быть пустым")
    if not test_mode:
        return validate_url(value)
    try:
        path = (base / value).resolve()
        with path.open("rb"):
            pass
    except (OSError, ValueError, RuntimeError) as error:
        raise ConfigError(f"repository: файл недоступен: {value}") from error
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
    display = read_display(parser, path.resolve().parent)
    return Settings(
        package, repository, test_mode, ascii_tree, reverse, display
    )


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


def read_display(
    parser: configparser.ConfigParser, base: Path
) -> DisplaySettings:
    """Проверить все параметры необязательной секции визуализации."""
    if VISUALIZATION_SECTION not in parser:
        return DisplaySettings()
    section = parser[VISUALIZATION_SECTION]
    render = read_boolean(section, "render", True)
    open_image = read_boolean(section, "open_image", render)
    if open_image and not render:
        raise ConfigError("open_image: требуется render=true")
    url = section.get("plantuml_url", DEFAULT_PLANTUML_URL).strip()
    validate_url(url, "plantuml_url")
    folder = section.get("output_dir", str(DEFAULT_OUTPUT)).strip()
    path = validate_output_dir(folder, base)
    return DisplaySettings(path, url.rstrip("/"), render, open_image)


def validate_output_dir(value: str, base: Path) -> Path:
    """Проверить путь; создание папки выполняется только при экспорте."""
    if not value or "\0" in value:
        raise ConfigError("output_dir: требуется корректный путь к каталогу")
    try:
        path = (base / value).resolve()
        if path.exists() and not path.is_dir():
            raise ConfigError("output_dir: указан файл вместо каталога")
    except (OSError, ValueError, RuntimeError) as error:
        raise ConfigError(f"output_dir: недопустимый путь: {error}") from error
    return path
