# Этап 1. Минимальный прототип с конфигурацией

Дата коммита: **04.11.2026, 19:17:00 +03:00**.

## Успешный запуск

```console
py -3 run.py --config config.ini
package=junit:junit:4.13.2
repository=https://repo.maven.apache.org/maven2
test_mode=false
ascii_tree=true
```

## Ошибки всех пользовательских параметров

```console
py -3 run.py --config examples/errors/package.ini
Ошибка: package: ожидаются координаты groupId:artifactId:version

py -3 run.py --config examples/errors/repository.ini
Ошибка: repository: ожидается абсолютный HTTP(S)-адрес

py -3 run.py --config examples/errors/test_mode.ini
Ошибка: test_mode: ожидается true или false

py -3 run.py --config examples/errors/ascii_tree.ini
Ошибка: ascii_tree: ожидается true или false
```

Каждый ошибочный запуск завершается с кодом `2`. Дополнительно тесты
проверяют пропущенные ключи, повторы, лишние секции, недоступные файлы,
некорректную кодировку, имя пакета и путь в тестовом режиме.

Вывод ключей предназначен только для первого этапа; в последующих
коммитах его заменит результат анализа зависимостей.
