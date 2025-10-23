#!/usr/bin/env python3
"""
Скрипт настройки PlummyPromo Telegram Bot
"""

import os
import sys
from pathlib import Path


def create_env_file():
    """Создать .env файл из примера"""
    env_example = Path(".env.example")
    env_file = Path(".env")
    
    if env_file.exists():
        print("⚠️  .env файл уже существует")
        response = input("Перезаписать? (y/N): ").lower()
        if response != 'y':
            return False
    
    if not env_example.exists():
        print("❌ Файл .env.example не найден")
        return False
    
    # Копируем содержимое
    env_file.write_text(env_example.read_text())
    print("✅ Создан файл .env")
    return True


def setup_database():
    """Настройка базы данных"""
    print("📊 Настройка базы данных...")
    
    # Импортируем и инициализируем БД
    try:
        from database.database import db
        import asyncio
        
        async def init_db():
            await db.init()
            print("✅ База данных инициализирована")
        
        asyncio.run(init_db())
        return True
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
        return False


def main():
    """Главная функция настройки"""
    print("🎉 Настройка PlummyPromo Telegram Bot")
    print("=" * 40)
    
    # Проверяем Python версию
    if sys.version_info < (3, 8):
        print("❌ Требуется Python 3.8 или выше")
        print(f"Текущая версия: {sys.version}")
        return False
    
    # Шаг 1: Создание .env файла
    print("\n1️⃣ Создание конфигурации...")
    if not create_env_file():
        return False
    
    # Шаг 2: Установка зависимостей
    print("\n2️⃣ Установка зависимостей...")
    print("Выполните команду: pip install -r requirements.txt")
    
    # Шаг 3: Настройка .env
    print("\n3️⃣ Настройка .env файла...")
    print("Отредактируйте файл .env и укажите:")
    print("• BOT_TOKEN - токен от @BotFather")
    print("• ADMIN_ID - ваш Telegram User ID")
    print("• SHOP_NAME - название магазина")  
    print("• SHOP_URL - URL магазина")
    
    # Шаг 4: База данных
    print("\n4️⃣ Инициализация базы данных...")
    response = input("Инициализировать базу данных? (Y/n): ").lower()
    if response != 'n':
        if not setup_database():
            print("⚠️  База данных не инициализирована")
    
    print("\n✅ Настройка завершена!")
    print("\n🚀 Для запуска бота выполните:")
    print("python main.py")
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n👋 Настройка прервана")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Ошибка настройки: {e}")
        sys.exit(1)
