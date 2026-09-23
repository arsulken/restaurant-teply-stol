# Ресторан «Тёплый стол»

Учебный проект команды из четырёх человек. Отдельные фронтенд и REST API.

## Запуск на macOS и Linux из корня репозитория

После скачивания ZIP откройте терминал в распакованной папке `restaurant-teply-stol-main`. При клонировании папка называется `restaurant-teply-stol`.

В первом терминале:

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r restaurant/backend/requirements.txt
python3 restaurant/backend/app.py
```

Если среда `.venv` уже создана и активирована, начните с установки зависимостей.

Во втором терминале, также из корня репозитория:

```sh
python3 -m http.server 8080 --bind 127.0.0.1 --directory restaurant/frontend
```

Откройте http://127.0.0.1:8080. Оба терминала должны оставаться открытыми. Для остановки нажмите Ctrl+C.

## Если не найден requirements.txt

Папка `backend` находится внутри `restaurant`. Из корня нужен путь `restaurant/backend/requirements.txt`. Команда с коротким путём `backend/requirements.txt` работает после перехода `cd restaurant`.

[Подробная инструкция, Windows и состав команды](restaurant/README.md)

Общий отчёт, четыре личных отчёта и презентация находятся в корне репозитория.
