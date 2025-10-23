#!/usr/bin/env python3
"""
Скрипт для обновления структуры базы данных
Добавляет новые поля для системы обратной связи
"""

import asyncio
import aiosqlite
from utils.config import Config

async def update_database():
    """Обновить структуру базы данных"""
    db_path = Config.DB_PATH
    
    print("=" * 50)
    print("ОБНОВЛЕНИЕ СТРУКТУРЫ БАЗЫ ДАННЫХ")
    print("=" * 50)
    
    try:
        async with aiosqlite.connect(db_path) as db:
            # Проверяем наличие поля feedback_requested в таблице promocodes
            cursor = await db.execute("PRAGMA table_info(promocodes)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            updates_applied = []
            
            # Добавляем поле feedback_requested если его нет
            if 'feedback_requested' not in column_names:
                print("\n➕ Добавление поля feedback_requested...")
                await db.execute("""
                    ALTER TABLE promocodes 
                    ADD COLUMN feedback_requested BOOLEAN DEFAULT 0
                """)
                updates_applied.append("feedback_requested")
            else:
                print("\n✓ Поле feedback_requested уже существует")
            
            # Добавляем поле feedback_request_date если его нет
            if 'feedback_request_date' not in column_names:
                print("➕ Добавление поля feedback_request_date...")
                await db.execute("""
                    ALTER TABLE promocodes 
                    ADD COLUMN feedback_request_date DATETIME NULL
                """)
                updates_applied.append("feedback_request_date")
            else:
                print("✓ Поле feedback_request_date уже существует")
            
            # Проверяем наличие таблицы feedback
            cursor = await db.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='feedback'
            """)
            table_exists = await cursor.fetchone()
            
            if not table_exists:
                print("➕ Создание таблицы feedback...")
                await db.execute("""
                    CREATE TABLE feedback (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        promo_code TEXT NOT NULL,
                        feedback_text TEXT NOT NULL,
                        created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                """)
                updates_applied.append("feedback table")
            else:
                print("✓ Таблица feedback уже существует")
            
            # Обновляем настройки промокодов (13%, 7 дней)
            print("\n⚙️  Обновление настроек промокодов...")
            
            # Проверяем текущие значения
            cursor = await db.execute("SELECT value FROM bot_settings WHERE key = 'promo_discount_percent'")
            current_discount = await cursor.fetchone()
            
            cursor = await db.execute("SELECT value FROM bot_settings WHERE key = 'promo_duration_days'")
            current_duration = await cursor.fetchone()
            
            if current_discount:
                print(f"   Текущая скидка: {current_discount[0]}%")
            if current_duration:
                print(f"   Текущий срок: {current_duration[0]} дней")
            
            # Устанавливаем новые значения
            await db.execute("""
                INSERT OR REPLACE INTO bot_settings (key, value, updated_date)
                VALUES ('promo_discount_percent', '13', datetime('now'))
            """)
            await db.execute("""
                INSERT OR REPLACE INTO bot_settings (key, value, updated_date)
                VALUES ('promo_duration_days', '7', datetime('now'))
            """)
            updates_applied.append("settings updated to 13% and 7 days")
            
            await db.commit()
            
            print("\n✅ Обновление завершено успешно!")
            
            if updates_applied:
                print(f"\n📊 Применено обновлений: {len(updates_applied)}")
                for update in updates_applied:
                    print(f"   ✓ {update}")
            else:
                print("\nℹ️  Все поля уже существуют, обновление не требуется")
            
            print(f"\n⚙️  Новые настройки промокодов:")
            print(f"   Скидка: 13%")
            print(f"   Срок действия: 7 дней")
            
    except Exception as e:
        print(f"\n❌ Ошибка при обновлении базы данных: {e}")
        return False
    
    print("\n" + "=" * 50)
    return True


if __name__ == "__main__":
    print("\nℹ️  Этот скрипт обновит структуру базы данных для поддержки новых функций:")
    print("   - Система обратной связи от пользователей")
    print("   - Обновление настроек промокодов (13%, 7 дней)")
    print("\n⚠️  Перед обновлением рекомендуется сделать резервную копию базы данных!")
    
    confirm = input("\nПродолжить обновление? (введите 'ДА' для подтверждения): ")
    
    if confirm.strip().upper() == "ДА":
        asyncio.run(update_database())
    else:
        print("\n❌ Операция отменена пользователем")

