"""Проверка структуры, содержимого и дат пяти Conventional Commits."""

import argparse
import re
import subprocess
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_PATHS = {"README.md", ".gitignore", "src", "tests"}
LAUNCHERS = {"run.sh", "run.bat", "Makefile"}
FORBIDDEN_PARTS = {
    "__pycache__", ".venv", "venv", ".idea", ".vscode", "output", "target",
    "build", "dist", ".pytest_cache", ".mypy_cache", ".ruff_cache",
}
FORBIDDEN_SUFFIXES = {
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".jar", ".whl",
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe", ".class", ".o", ".a",
}
CONVENTIONAL = re.compile(r"^[a-z]+\([a-z][a-z0-9-]*\): .+$")
RUSSIAN = re.compile(r"[А-Яа-яЁё]")
STAGE_COUNT = 5
FIRST_DATE = date(2026, 11, 4)
EARLIEST_TIME = time(19, 1)
LATEST_TIME = time(23, 54)


def git_output(arguments: list[str]) -> str:
    """Прочитать метаданные Git без изменения конфигурации или истории."""
    result = subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True,
        text=True, encoding="utf-8",
    )
    return result.stdout


def repository_files() -> list[Path]:
    """Учитывать индекс и новые неигнорируемые файлы перед коммитом."""
    output = git_output([
        "ls-files", "-z", "--cached", "--others", "--exclude-standard",
    ])
    return [Path(name) for name in output.split("\0") if name]


def check_structure(files: list[Path]) -> list[str]:
    """Проверить обязательные пути и наличие скрипта запуска в репозитории."""
    top_level = {path.parts[0] for path in files}
    errors = [f"Отсутствует {name}" for name in REQUIRED_PATHS - top_level]
    if not top_level & LAUNCHERS:
        errors.append("Отсутствует скрипт запуска")
    return errors


def check_content(path: Path) -> list[str]:
    """Отклонить архивы, бинарные файлы, кеши и артефакты редакторов/сборки."""
    errors = []
    if set(path.parts) & FORBIDDEN_PARTS:
        errors.append(f"Служебный или сгенерированный путь: {path}")
    if path.suffix.lower() in FORBIDDEN_SUFFIXES:
        errors.append(f"Архив или бинарный/служебный файл: {path}")
    data = (ROOT / path).read_bytes()
    try:
        text = data.decode("utf-8-sig")
        if "\0" in text:
            errors.append(f"Бинарное содержимое: {path}")
    except UnicodeDecodeError:
        errors.append(f"Нетекстовый файл: {path}")
    return errors


def check_commit(record: str, index: int) -> list[str]:
    """Проверить русский заголовок и обе даты отдельного этапа."""
    subject, author_date, committer_date = record.split("\x1f")
    errors = []
    if not CONVENTIONAL.fullmatch(subject) or not RUSSIAN.search(subject):
        errors.append(f"Неверное оформление коммита: {subject}")
    expected = FIRST_DATE + timedelta(days=index)
    for value in (author_date, committer_date):
        stamp = datetime.fromisoformat(value)
        clock = stamp.time()
        if stamp.date() != expected:
            errors.append(f"Неверная дата этапа {index + 1}: {value}")
        if not EARLIEST_TIME <= clock <= LATEST_TIME:
            errors.append(f"Время вне заданного интервала: {value}")
    if author_date != committer_date:
        errors.append(f"Различаются author/committer date: {subject}")
    return errors


def check_history() -> list[str]:
    """Проверить пять последовательных коммитов и чистоту рабочего дерева."""
    records = git_output([
        "log", "--reverse", "--format=%s%x1f%aI%x1f%cI",
    ]).splitlines()
    errors = []
    if len(records) != STAGE_COUNT:
        actual = len(records)
        errors.append(f"Ожидалось {STAGE_COUNT} коммитов, найдено {actual}")
    for index, record in enumerate(records):
        errors.extend(check_commit(record, index))
    if git_output(["status", "--porcelain"]).strip():
        errors.append("Рабочее дерево содержит несохранённые изменения")
    return errors


def main() -> int:
    """Проверить оформление; историю проверять по отдельному флагу."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true")
    args = parser.parse_args()
    files = repository_files()
    errors = check_structure(files)
    for path in files:
        errors.extend(check_content(path))
    if args.history:
        errors.extend(check_history())
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Репозиторий: {len(files)} текстовых файлов; нарушения не найдены.")
    if args.history:
        print("История: 5 русских Conventional Commits, даты и время верны.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
