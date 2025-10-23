#!/bin/bash

source venv/bin/activate

# Скрипт запуска PlummyPromo Telegram Bot

echo "🎉 Запуск PlummyPromo Telegram Bot"
echo "=================================="

# Проверяем наличие Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не установлен"
    exit 1
fi

# Проверяем наличие .env файла
if [ ! -f ".env" ]; then
    echo "❌ Файл .env не найден"
    echo "Запустите: python setup.py"
    exit 1
fi

# Проверяем наличие базы данных
if [ ! -f "bot_database.db" ]; then
    echo "🔄 Инициализация базы данных..."
    python3 -c "
import asyncio
from database.database import db

async def init():
    await db.init()
    print('✅ База данных инициализирована')

asyncio.run(init())
"
fi

# Запускаем бота
echo "🚀 Запускаем бота..."
python3 main.py
