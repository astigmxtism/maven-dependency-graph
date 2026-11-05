# Этап 2. Сбор данных

Дата коммита: **05.11.2026, 20:26:00 +03:00**.

Приложение самостоятельно строит URL:

```text
{repository}/{groupId с / вместо .}/{artifactId}/{version}/{artifactId}-{version}.pom
```

Загрузка — `urllib.request`, XML — `xml.etree.ElementTree`.
Менеджеры пакетов и сторонние библиотеки для анализа не используются.
POM родителей и импортированных BOM читаются тем же способом.

## Реализованная семантика

- Namespace Maven и XML без namespace.
- Только `project/dependencies`, без зависимостей плагинов и профилей.
- Наследование координат, свойств, объявлений и `dependencyManagement`.
- `${name}`, `${project.version}`, `${pom.version}`, свойства parent.
- Импорт BOM (`type=pom`, `scope=import`), собственный контекст его свойств.
- Версии, области, optional, type, classifier и exclusions.
- Кеширование POM в памяти; обнаружение циклов parent/BOM и свойств.
- Ошибки HTTP, таймауты, ограничение размера ответа и ошибки XML.

На этом этапе выводятся **все прямые объявления**, в том числе `test`,
`provided` и `optional`. Управляемые зависимости сами по себе рёбер не создают.
Родительские POM также не являются зависимостями пакета.

## Примеры

```console
py -3 run.py --config examples/maven/junit.ini
Прямые зависимости junit:junit:4.13.2:
org.hamcrest:hamcrest-core:1.3 [compile]
org.hamcrest:hamcrest-library:1.3 [test]
```

Другие реальные POM, использующие родительское управление версиями:

```console
py -3 run.py --config examples/maven/slf4j.ini
Прямые зависимости org.slf4j:slf4j-simple:2.0.16:
junit:junit:4.13.1 [test]
org.slf4j:slf4j-api:2.0.16 [compile]
org.slf4j:slf4j-api:2.0.16 [test]

py -3 run.py --config examples/maven/httpclient.ini
Прямые зависимости org.apache.httpcomponents:httpclient:4.5.14:
org.apache.httpcomponents:httpcore:4.4.16 [compile]
commons-logging:commons-logging:1.2 [compile]
commons-codec:commons-codec:1.11 [compile]
junit:junit:4.11 [test]
org.mockito:mockito-core:1.10.19 [test]
```

Это результаты реальных HTTP-запросов. Повторное объявление `slf4j-api`
имеет `type=test-jar`; оно не объединяется с обычной jar-зависимостью.
JUnit у SLF4J наследуется от родителя.

## Границы модели

Анализируются опубликованные release-POM в одном заданном репозитории.
Диапазоны версий, `LATEST`, `RELEASE` и timestamped SNAPSHOT не разрешаются:
при их использовании выдаётся ошибка вместо выдуманной версии.
Профили, настройки сборочной машины, `relativePath`, relocation и дополнительные
репозитории из POM не активируются. Поддержка этих механизмов потребовала бы
воспроизведения контекста сборки Maven.

Вывод списка прямых зависимостей предназначен для второго этапа;
на следующем этапе он заменяется графом транзитивных зависимостей.
