# JiraInsight
## _Модуль для синхронизации объектов из сторонних источников со схемой в Insight_


[![Build Status](https://travis-ci.org/joemccann/dillinger.svg?branch=master)](https://travis-ci.org/joemccann/dillinger)


## Возможности

- Синхронизация объектов с JSON файлов
- Использование имён для автоматического определения id атрибутов и объектов
- Обновление объектов
- Создание объектов
- Проверка на наличие объектов
- Удаление объектов

В зависимости от задач, можно сравнивать объекты из двух источников данных. 
По результатам принимать решение об удаление объекта или его отключении.
Наличие класса Mixer. На вход подаётся список Атрибут: значение. С указанием типа объекта в схеме Insight.
На выход готовые словари для передачи внутренним методам ✨create_object и update_object.✨
> Note: Ключём для связки объектов является поле `Name`. 
Измените константу `KEY_ATTRIBUTE` если небходима связка по другому атрибуту.


## Технологии

В процессе разработки использовались следующие инструменты:

- [Python] - Язык разработки.
- [Visual Studio Code] - IDE
- [GitLab] - Git сервер.
- [JIRA Insight API] - Документация на API JIRA Insight

## Установка

Требуется [Python] 3.8.5+ для работы.
Для установки сделайте клонирование репозитория.
Для примера:

```sh
cd /usr/local/scripts
git clone git@gitlab.kalashnikovconcern.ru:kovo/jirainsight_project.git

```

Установите зависимости.

```sh
pip install -r requirements.txt 
```

Установите сам пакет

```sh
pip install .
```

## Как использовать

Объявите данные для подключения:

```python
    login = "_Login for access to Insight_"
    password = "same_pass"
    jira_url = "https://sd.kalashnikovconcern.ru"
    schema_name = "CMDB"
    object_type_name = "Ethernet Switches[MMZ]"
```
Или используйте их сразу при передаче значений. 
Рекомендуется использовать ConfigParser

Создайте объекты подключения к серверу JIRA, целевой схеме и типа объекта в схеме:

```python
    jira = Insight(jira_url, login, password)
    schema = InsightSchema(jira, schema_name)
    schema_obj_type = schema.get_object_type(object_type_name)
```

Загрузите данные из источника, например через файл JSON или импорта с другого API в класс DataSource и передайте данные классу Mixer:

```python
    raw_list = 'filedump.json'
    source = DataSource(raw_list, schema_obj_type)
    mixer = Mixer(source, schema)
```

Пример, для обновления данных в схеме Insight:

```python
    # Получение имён в схеме и источнике
    update_objects = mixer.make_dicts_for_update_schema_objects()
    failed = []
    for key, value in update_objects.items():
        mixer.object_type.objects
        schema_object = mixer.object_type.objects[key]
        try:
            schema_object.update_object(value)
        except Exception as e:
            print(e)
            failed.append(key)
```


## Автор

Кокорников Илья 



[//]: # (These are reference links used in the body of this note and get stripped out when the markdown processor does its job. There is no need to format nicely because it shouldn't be seen. Thanks SO - http://stackoverflow.com/questions/4823468/store-comments-in-markdown-syntax)



   [Python]: <https://www.python.org>
   [Visual Studio Code]: <https://code.visualstudio.com/>
   [GitLab]: <https://gitlab.com/gitlab-org>
   [JIRA Insight API]: <https://documentation.mindville.com/display/ICV50/Version+1.0+documentation>

