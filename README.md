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

```cmd
scripts\run_bot.cmd
```

Можно передавать дополнительные аргументы, они будут проброшены в `python -m space_aces_bot`:

```cmd
scripts\run_bot.cmd --some-arg value
```

