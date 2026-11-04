"""Проверки ограничений оформления на основе AST стандартного Python."""

import ast
import re
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_FILE_LINES = 1000
MAX_PYTHON_LINE = 80
MAX_CODE_LINE = 120
MAX_FUNCTION_LINES = 40
MAX_ARGUMENTS = 7
MAX_COMPLEXITY = 10
BASE_COMPLEXITY = 1
IGNORED_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "output", "target",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "build", "dist",
}
CODE_SUFFIXES = {".py", ".sh", ".bat"}
SNAKE_CASE = re.compile(r"[a-z_][a-z0-9_]*\Z")
CAMEL_CASE = re.compile(r"[A-Z][A-Za-z0-9]*\Z")
UNITTEST_HOOKS = {"setUp", "tearDown", "setUpClass", "tearDownClass"}


def decision_cost(node: ast.AST) -> int:
    """Посчитать ветвления, включая короткие логические вычисления."""
    branches = (
        ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler,
        ast.IfExp,
    )
    if isinstance(node, branches):
        return BASE_COMPLEXITY
    if isinstance(node, ast.BoolOp):
        return len(node.values) - BASE_COMPLEXITY
    if isinstance(node, ast.comprehension):
        return BASE_COMPLEXITY + len(node.ifs)
    if isinstance(node, ast.Match):
        return len(node.cases)
    return 0


def check_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Проверить размер, аргументы, сложность, имя и документацию."""
    errors = []
    size = node.end_lineno - node.lineno + 1
    args = node.args
    count = len(args.posonlyargs) + len(args.args) + len(args.kwonlyargs)
    count += bool(args.vararg) + bool(args.kwarg)
    complexity = BASE_COMPLEXITY + sum(
        decision_cost(child) for child in ast.walk(node)
    )
    metrics = (
        (size, MAX_FUNCTION_LINES, "длина функции"),
        (count, MAX_ARGUMENTS, "аргументы"),
        (complexity, MAX_COMPLEXITY, "сложность"),
    )
    for value, limit, label in metrics:
        if value > limit:
            errors.append(f"{node.name}: {label} {value} > {limit}")
    if not ast.get_docstring(node):
        errors.append(f"{node.name}: отсутствует docstring")
    if not SNAKE_CASE.fullmatch(node.name) and node.name not in UNITTEST_HOOKS:
        errors.append(f"{node.name}: имя не соответствует PEP 8")
    return errors


def is_number(node: ast.AST) -> bool:
    """Распознать числовой литерал, в том числе со знаком."""
    if isinstance(node, ast.UnaryOp):
        return is_number(node.operand)
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float, complex))
        and not isinstance(node.value, bool)
    )


def check_ast(tree: ast.Module) -> list[str]:
    """Проверить определения и магические числа в сравнениях."""
    errors = []
    if not ast.get_docstring(tree):
        errors.append("отсутствует docstring модуля")
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            errors.extend(check_function(node))
        if isinstance(node, ast.ClassDef):
            valid_name = CAMEL_CASE.fullmatch(node.name)
            if not valid_name or not ast.get_docstring(node):
                errors.append(f"{node.name}: имя класса или docstring")
        if isinstance(node, ast.Compare):
            if any(is_number(part) for part in [node.left, *node.comparators]):
                errors.append(f"строка {node.lineno}: число в сравнении")
    return errors


def check_lines(path: Path, text: str) -> list[str]:
    """Проверить число строк файла и длину строк исходного кода."""
    lines = text.splitlines()
    errors = []
    if len(lines) > MAX_FILE_LINES:
        errors.append(f"число строк {len(lines)} > {MAX_FILE_LINES}")
    if path.suffix not in CODE_SUFFIXES:
        return errors
    limit = MAX_PYTHON_LINE if path.suffix == ".py" else MAX_CODE_LINE
    for number, line in enumerate(lines, start=1):
        if len(line) > limit:
            errors.append(f"строка {number}: длина {len(line)} > {limit}")
    return errors


def check_file(path: Path) -> list[str]:
    """Проверить один текстовый файл, а для Python также AST и комментарии."""
    text = path.read_text(encoding="utf-8-sig")
    errors = check_lines(path, text)
    if path.suffix == ".py":
        errors.extend(check_ast(ast.parse(text, filename=str(path))))
        with path.open("rb") as stream:
            for token in tokenize.tokenize(stream.readline):
                if token.type == tokenize.COMMENT:
                    errors.append(f"строка {token.start[0]}: нужен docstring")
    return errors


def main() -> int:
    """Проверить проект и вернуть ненулевой код при нарушениях."""
    errors = []
    for path in sorted(ROOT.rglob("*")):
        relative = path.relative_to(ROOT)
        if not path.is_file() or set(relative.parts) & IGNORED_DIRS:
            continue
        for error in check_file(path):
            errors.append(f"{relative}: {error}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Оформление: все проверки пройдены.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
