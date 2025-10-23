# Используем официальный образ Python
FROM python:3.12-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все файлы проекта
COPY . .

# Создаем директорию для базы данных
RUN mkdir -p /app/data

# Переменные окружения по умолчанию (могут быть переопределены)
ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite:///bot_database.db

# Скрипт инициализации и запуска
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
echo "🎉 Запуск PlummyPromo Telegram Bot"\n\
echo "=================================="\n\
\n\
# Инициализация базы данных если её нет\n\
if [ ! -f "bot_database.db" ]; then\n\
    echo "🔄 Инициализация базы данных..."\n\
    python3 -c "\
import asyncio\n\
from database.database import db\n\
\n\
async def init():\n\
    await db.init()\n\
    print('\''✅ База данных инициализирована'\'')\n\
\n\
asyncio.run(init())\n\
"\n\
fi\n\
\n\
# Запускаем бота\n\
echo "🚀 Запускаем бота..."\n\
exec python3 main.py\n\
' > /app/start.sh && chmod +x /app/start.sh

# Запуск бота
CMD ["/app/start.sh"]

