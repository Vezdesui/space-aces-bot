# space_aces_bot skeleton

Это скелет бота для игры / проекта Space Aces.  
Сейчас он только читает конфиг и выводит минимальную информацию в лог.

## Подготовка окружения

1. Активировать виртуальное окружение:
   ```cmd
   .venv\Scripts\activate.bat
   ```

2. Установить зависимости:
   ```cmd
   pip install -r requirements.txt
   ```

## Конфигурация

Пример конфига лежит в `configs\config.example.json`.  
Можно либо отредактировать его, либо скопировать в `configs\config.json` и настроить под себя.

## Запуск бота

Используйте скрипт:

## Credentials / учетные данные

- Логин и пароль не должны попадать в репозиторий.
- Для этого используется файл `.env`, который игнорируется `git` (строка уже добавлена в `.gitignore`).
- Пример содержимого `.env`:

  ```env
  SPACE_ACES_USERNAME=YOUR_USERNAME
  SPACE_ACES_PASSWORD=YOUR_PASSWORD
  ```

- Для ориентира есть файл `.env.example` в корне проекта: его можно скопировать в `.env` и заполнить реальными значениями.
- `configs\config.example.json` содержит только пример логина/пароля, а реальные значения берутся из `.env` через `python-dotenv` (переменные `SPACE_ACES_USERNAME` и `SPACE_ACES_PASSWORD`).

```cmd
scripts\run_bot.cmd
```

Можно передавать дополнительные аргументы, они будут проброшены в `python -m space_aces_bot`:

```cmd
scripts\run_bot.cmd --some-arg value
```
