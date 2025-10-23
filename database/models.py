"""
Модели базы данных для телеграм бота PlummyPromo
"""

import sqlite3
import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict, Any
import uuid
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Менеджер для работы с базой данных"""
    
    def __init__(self, db_path: str = "bot_database.db"):
        self.db_path = db_path
    
    def get_connection(self):
        """Получить соединение с базой данных"""
        return aiosqlite.connect(self.db_path)
    
    async def init_database(self):
        """Инициализация базы данных и создание таблиц"""
        async with aiosqlite.connect(self.db_path) as db:
            # Таблица пользователей
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    phone TEXT,
                    registration_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,
                    referral_source TEXT,
                    is_blocked BOOLEAN DEFAULT 0,
                    notifications_enabled BOOLEAN DEFAULT 1
                )
            """)
            
            # Таблица промокодов
            await db.execute("""
                CREATE TABLE IF NOT EXISTS promocodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                used_date DATETIME NULL,
                is_used BOOLEAN DEFAULT 0,
                discount_percent INTEGER DEFAULT 10,
                order_id TEXT NULL,
                woocommerce_id INTEGER NULL,
                woocommerce_synced BOOLEAN DEFAULT 0,
                sync_error TEXT NULL,
                notification_5_days_sent BOOLEAN DEFAULT 0,
                notification_3_days_sent BOOLEAN DEFAULT 0,
                notification_1_day_sent BOOLEAN DEFAULT 0,
                notification_5_days_date DATETIME NULL,
                notification_3_days_date DATETIME NULL,
                notification_1_day_date DATETIME NULL,
                feedback_requested BOOLEAN DEFAULT 0,
                feedback_request_date DATETIME NULL,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            # Таблица статистики переходов
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    session_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    referral_source TEXT,
                    utm_source TEXT,
                    utm_medium TEXT,
                    utm_campaign TEXT,
                    action_type TEXT, -- 'start', 'promo_request', 'faq_view' etc.
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            # Таблица сообщений для рассылки
            await db.execute("""
                CREATE TABLE IF NOT EXISTS broadcast_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_text TEXT NOT NULL,
                    created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    sent_count INTEGER DEFAULT 0,
                    delivered_count INTEGER DEFAULT 0,
                    is_completed BOOLEAN DEFAULT 0
                )
            """)
            
            # Таблица настроек бота
            await db.execute("""
                CREATE TABLE IF NOT EXISTS bot_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_date DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица обратной связи
            await db.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    promo_code TEXT NOT NULL,
                    feedback_text TEXT NOT NULL,
                    created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            await db.commit()
            
            # Инициализируем настройки по умолчанию
            await self._init_default_settings(db)
    
    async def _init_default_settings(self, db):
        """Инициализировать настройки по умолчанию если их нет"""
        try:
            from datetime import datetime
            
            # Настройки по умолчанию
            default_settings = {
                'promo_discount_percent': '13',  # 13% скидка
                'promo_duration_days': '7'       # 7 дней действие
            }
            
            for key, value in default_settings.items():
                # Проверяем, есть ли настройка
                cursor = await db.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
                existing = await cursor.fetchone()
                
                if not existing:
                    # Добавляем настройку по умолчанию
                    await db.execute("""
                        INSERT INTO bot_settings (key, value, updated_date)
                        VALUES (?, ?, ?)
                    """, (key, value, datetime.now().isoformat()))
                    logger.info(f"✅ Установлена настройка по умолчанию: {key} = {value}")
            
            await db.commit()
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации настроек по умолчанию: {e}")


class User:
    """Модель пользователя"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    async def get_or_create_user(self, user_id: int, username: str = None, 
                                first_name: str = None, last_name: str = None,
                                referral_source: str = None) -> Dict[str, Any]:
        """Получить существующего пользователя или создать нового"""
        async with aiosqlite.connect(self.db.db_path) as db:
            # Проверяем существование пользователя
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                user = await cursor.fetchone()
            
            if user:
                # Обновляем последнюю активность
                await db.execute(
                    "UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE user_id = ?",
                    (user_id,)
                )
                await db.commit()
                
                # Преобразуем в словарь
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, user))
            else:
                # Создаем нового пользователя
                await db.execute("""
                    INSERT INTO users (user_id, username, first_name, last_name, referral_source)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, username, first_name, last_name, referral_source))
                await db.commit()
                
                # Возвращаем созданного пользователя
                async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                    user = await cursor.fetchone()
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, user))
    
    async def update_user_phone(self, user_id: int, phone: str) -> bool:
        """Обновить номер телефона пользователя"""
        async with aiosqlite.connect(self.db.db_path) as db:
            await db.execute(
                "UPDATE users SET phone = ? WHERE user_id = ?",
                (phone, user_id)
            )
            await db.commit()
            return True
    
    async def get_all_active_users(self) -> List[Dict[str, Any]]:
        """Получить всех активных пользователей для рассылки"""
        async with aiosqlite.connect(self.db.db_path) as db:
            async with db.execute("""
                SELECT * FROM users 
                WHERE is_blocked = 0 AND notifications_enabled = 1
                ORDER BY registration_date DESC
            """) as cursor:
                users = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, user)) for user in users]
    
    async def get_users_count(self) -> int:
        """Получить общее количество пользователей"""
        async with aiosqlite.connect(self.db.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                result = await cursor.fetchone()
                return result[0] if result else 0


class PromoCode:
    """Модель промокода"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self._settings = None  # Будет инициализирован при первом обращении
    
    async def create_promo_code(self, user_id: int, discount_percent: int = None) -> str:
        """Создать новый промокод для пользователя с интеграцией в WooCommerce"""
        # Если процент скидки не указан, получаем из настроек
        if discount_percent is None:
            if self._settings is None:
                self._settings = Settings(self.db)
            discount_percent = await self._settings.get_promo_discount_percent()
            
        # Генерируем уникальный код
        code = f"PLUMMY{uuid.uuid4().hex[:6].upper()}"
        
        async with aiosqlite.connect(self.db.db_path) as db:
            # Проверяем, что код уникальный
            async with db.execute("SELECT id FROM promocodes WHERE code = ?", (code,)) as cursor:
                existing = await cursor.fetchone()
                if existing:
                    # Если код существует, генерируем новый
                    return await self.create_promo_code(user_id, discount_percent)
            
            # Создаем промокод локально сначала
            await db.execute("""
                INSERT INTO promocodes (code, user_id, discount_percent)
                VALUES (?, ?, ?)
            """, (code, user_id, discount_percent))
            await db.commit()
            
            logger.info(f"✅ Промокод {code} создан локально для пользователя {user_id}")
            
        # Пытаемся создать купон в WooCommerce 
        try:
            woo_result = await self._create_woocommerce_coupon(code, user_id, discount_percent)
            
            # Обновляем статус синхронизации
            async with aiosqlite.connect(self.db.db_path) as db:
                if woo_result["success"]:
                    await db.execute("""
                        UPDATE promocodes 
                        SET woocommerce_id = ?, woocommerce_synced = 1 
                        WHERE code = ?
                    """, (woo_result.get("woocommerce_id"), code))
                    logger.info(f"✅ Промокод {code} синхронизирован с WooCommerce (ID: {woo_result.get('woocommerce_id')})")
                else:
                    await db.execute("""
                        UPDATE promocodes 
                        SET sync_error = ?, woocommerce_synced = 0
                        WHERE code = ?
                    """, (woo_result.get("error", "Unknown error"), code))
                    logger.warning(f"⚠️ Промокод {code} создан локально, но не синхронизирован с WooCommerce: {woo_result.get('error')}")
                
                await db.commit()
                
        except Exception as e:
            # При ошибке WooCommerce, промокод остается в локальной базе
            logger.error(f"❌ Ошибка синхронизации промокода {code} с WooCommerce: {str(e)}")
            
            # Отмечаем ошибку синхронизации
            async with aiosqlite.connect(self.db.db_path) as db:
                await db.execute("""
                    UPDATE promocodes 
                    SET sync_error = ?, woocommerce_synced = 0
                    WHERE code = ?
                """, (str(e), code))
                await db.commit()
        
        return code
    
    async def _create_woocommerce_coupon(self, code: str, user_id: int, discount_percent: int) -> Dict[str, Any]:
        """Создать купон в WooCommerce"""
        try:
            # Импортируем WooCommerce менеджер
            from utils.woocommerce import woo_manager
            
            if not woo_manager.is_enabled():
                return {
                    "success": False,
                    "error": "WooCommerce интеграция отключена"
                }
            
            # Создаем купон в WooCommerce
            result = await woo_manager.create_coupon(
                coupon_code=code,
                user_id=user_id,
                discount_percent=discount_percent,
                usage_limit=1
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка создания купона в WooCommerce: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_user_promo_codes(self, user_id: int) -> List[Dict[str, Any]]:
        """Получить все промокоды пользователя"""
        async with aiosqlite.connect(self.db.db_path) as db:
            async with db.execute("""
                SELECT * FROM promocodes 
                WHERE user_id = ? 
                ORDER BY created_date DESC
            """, (user_id,)) as cursor:
                codes = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, code)) for code in codes]
    
    async def use_promo_code(self, code: str, order_id: str = None) -> bool:
        """Отметить промокод как использованный"""
        async with aiosqlite.connect(self.db.db_path) as db:
            result = await db.execute("""
                UPDATE promocodes 
                SET is_used = 1, used_date = CURRENT_TIMESTAMP, order_id = ?
                WHERE code = ? AND is_used = 0
            """, (order_id, code))
            await db.commit()
            
            success = result.rowcount > 0
            
            # Если промокод успешно отмечен как использованный в локальной базе,
            # попытаемся синхронизировать с WooCommerce
            if success:
                try:
                    from utils.woocommerce import woo_manager
                    woo_result = await woo_manager.mark_coupon_as_used(code)
                    if woo_result["success"]:
                        logger.info(f"✅ Промокод {code} отмечен как использованный в WooCommerce")
                    else:
                        logger.warning(f"⚠️ Промокод {code} отмечен в локальной базе, но не синхронизирован с WooCommerce: {woo_result.get('error')}")
                except Exception as e:
                    logger.error(f"Ошибка при синхронизации промокода {code} с WooCommerce: {str(e)}")
            
            return success
    
    async def get_promo_stats(self) -> Dict[str, Any]:
        """Получить статистику по промокодам"""
        async with aiosqlite.connect(self.db.db_path) as db:
            # Общее количество промокодов
            async with db.execute("SELECT COUNT(*) FROM promocodes") as cursor:
                total = (await cursor.fetchone())[0]
            
            # Использованные промокоды
            async with db.execute("SELECT COUNT(*) FROM promocodes WHERE is_used = 1") as cursor:
                used = (await cursor.fetchone())[0]
            
            # Статистика синхронизации с WooCommerce
            async with db.execute("SELECT COUNT(*) FROM promocodes WHERE woocommerce_synced = 1") as cursor:
                synced = (await cursor.fetchone())[0]
                
            async with db.execute("SELECT COUNT(*) FROM promocodes WHERE woocommerce_synced = 0 AND sync_error IS NOT NULL") as cursor:
                sync_errors = (await cursor.fetchone())[0]
            
            return {
                "total_generated": total,
                "total_used": used,
                "usage_rate": round((used / total * 100) if total > 0 else 0, 2),
                "woocommerce_synced": synced,
                "sync_errors": sync_errors,
                "sync_rate": round((synced / total * 100) if total > 0 else 0, 2)
            }
    
    async def get_unsynced_promocodes(self) -> List[Dict[str, Any]]:
        """Получить промокоды, не синхронизированные с WooCommerce"""
        async with aiosqlite.connect(self.db.db_path) as db:
            async with db.execute("""
                SELECT * FROM promocodes 
                WHERE woocommerce_synced = 0
                ORDER BY created_date DESC
            """) as cursor:
                codes = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, code)) for code in codes]
    
    async def retry_woocommerce_sync(self, code: str) -> bool:
        """Повторить синхронизацию промокода с WooCommerce"""
        async with aiosqlite.connect(self.db.db_path) as db:
            # Получаем информацию о промокоде
            async with db.execute("""
                SELECT user_id, discount_percent FROM promocodes 
                WHERE code = ? AND woocommerce_synced = 0
            """, (code,)) as cursor:
                promo_info = await cursor.fetchone()
                
                if not promo_info:
                    return False
                
                user_id, discount_percent = promo_info
                
                # Пытаемся создать купон в WooCommerce
                woo_result = await self._create_woocommerce_coupon(code, user_id, discount_percent)
                
                if woo_result["success"]:
                    await db.execute("""
                        UPDATE promocodes 
                        SET woocommerce_id = ?, woocommerce_synced = 1, sync_error = NULL
                        WHERE code = ?
                    """, (woo_result["woocommerce_id"], code))
                    await db.commit()
                    return True
                else:
                    await db.execute("""
                        UPDATE promocodes 
                        SET sync_error = ?
                        WHERE code = ?
                    """, (woo_result.get("error", "Unknown error"), code))
                    await db.commit()
                    return False


class Analytics:
    """Модель аналитики"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    async def track_user_action(self, user_id: int, action_type: str, 
                               referral_source: str = None, utm_data: Dict[str, str] = None):
        """Отследить действие пользователя"""
        async with aiosqlite.connect(self.db.db_path) as db:
            await db.execute("""
                INSERT INTO user_sessions (user_id, action_type, referral_source, utm_source, utm_medium, utm_campaign)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_id, action_type, referral_source,
                utm_data.get('utm_source') if utm_data else None,
                utm_data.get('utm_medium') if utm_data else None,
                utm_data.get('utm_campaign') if utm_data else None
            ))
            await db.commit()
    
    async def get_traffic_stats(self, days: int = 30) -> Dict[str, Any]:
        """Получить статистику трафика за последние дни"""
        async with aiosqlite.connect(self.db.db_path) as db:
            # Общая статистика переходов
            async with db.execute("""
                SELECT 
                    COUNT(DISTINCT user_id) as unique_users,
                    COUNT(*) as total_sessions,
                    referral_source,
                    COUNT(*) as sessions_count
                FROM user_sessions 
                WHERE session_date >= datetime('now', '-{} days')
                GROUP BY referral_source
            """.format(days)) as cursor:
                traffic_by_source = await cursor.fetchall()
            
            # Статистика по дням
            async with db.execute("""
                SELECT 
                    DATE(session_date) as date,
                    COUNT(DISTINCT user_id) as unique_users,
                    COUNT(*) as sessions
                FROM user_sessions 
                WHERE session_date >= datetime('now', '-{} days')
                GROUP BY DATE(session_date)
                ORDER BY date DESC
            """.format(days)) as cursor:
                daily_stats = await cursor.fetchall()
            
            return {
                "traffic_by_source": [
                    {"source": row[2] or "direct", "users": row[0], "sessions": row[3]}
                    for row in traffic_by_source
                ],
                "daily_stats": [
                    {"date": row[0], "unique_users": row[1], "sessions": row[2]}
                    for row in daily_stats
                ]
            }
    
    async def get_conversion_stats(self) -> Dict[str, float]:
        """Получить статистику конверсии"""
        async with aiosqlite.connect(self.db.db_path) as db:
            # Пользователи, которые начали работу с ботом
            async with db.execute("""
                SELECT COUNT(DISTINCT user_id) FROM user_sessions 
                WHERE action_type = 'start'
            """) as cursor:
                started_users = (await cursor.fetchone())[0]
            
            # Пользователи, которые получили промокод
            async with db.execute("""
                SELECT COUNT(DISTINCT user_id) FROM promocodes
            """) as cursor:
                promo_users = (await cursor.fetchone())[0]
            
            # Пользователи, которые использовали промокод
            async with db.execute("""
                SELECT COUNT(DISTINCT user_id) FROM promocodes 
                WHERE is_used = 1
            """) as cursor:
                converted_users = (await cursor.fetchone())[0]
            
            return {
                "start_to_promo": round((promo_users / started_users * 100) if started_users > 0 else 0, 2),
                "promo_to_purchase": round((converted_users / promo_users * 100) if promo_users > 0 else 0, 2),
                "overall_conversion": round((converted_users / started_users * 100) if started_users > 0 else 0, 2)
            }


class Settings:
    """Модель настроек бота"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    async def get_setting(self, key: str, default_value: str = None) -> str:
        """Получить значение настройки"""
        async with aiosqlite.connect(self.db_manager.db_path) as db:
            async with db.execute("""
                SELECT value FROM bot_settings WHERE key = ?
            """, (key,)) as cursor:
                result = await cursor.fetchone()
                return result[0] if result else default_value
    
    async def set_setting(self, key: str, value: str) -> bool:
        """Сохранить настройку"""
        try:
            async with aiosqlite.connect(self.db_manager.db_path) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO bot_settings (key, value, updated_date)
                    VALUES (?, ?, ?)
                """, (key, value, datetime.now().isoformat()))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка сохранения настройки {key}: {e}")
            return False
    
    async def get_promo_discount_percent(self) -> int:
        """Получить процент скидки для промокодов"""
        value = await self.get_setting('promo_discount_percent')
        if value:
            try:
                return int(value)
            except ValueError:
                logger.error(f"Некорректное значение процента скидки: {value}")
        
        # Если настройка не найдена, возвращаем значение по умолчанию
        try:
            from utils.config import Config
            return Config.PROMO_DISCOUNT_PERCENT
        except ImportError:
            return 10  # Дефолтное значение, если Config недоступен
    
    async def set_promo_discount_percent(self, percent: int) -> bool:
        """Установить процент скидки для промокодов"""
        return await self.set_setting('promo_discount_percent', str(percent))
    
    async def get_promo_duration_days(self) -> int:
        """Получить срок действия промокодов в днях"""
        value = await self.get_setting('promo_duration_days')
        if value:
            try:
                return int(value)
            except ValueError:
                logger.error(f"Некорректное значение срока действия: {value}")
        return 7  # По умолчанию 7 дней
    
    async def set_promo_duration_days(self, days: int) -> bool:
        """Установить срок действия промокодов в днях"""  
        return await self.set_setting('promo_duration_days', str(days))
