"""Запуск приложения без установки пакета и внешних зависимостей."""

import sys
from pathlib import Path


def main() -> int:
    """Добавить каталог исходного кода и вызвать CLI."""
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    from maven_graph.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
