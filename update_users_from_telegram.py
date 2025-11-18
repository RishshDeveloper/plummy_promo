"""
Скрипт для обновления информации о пользователях из Telegram
Получает username пользователей по их ID через Bot API
"""

import asyncio
import logging
from database.database import db
from utils.config import Config
from telegram import Bot
from telegram.error import TelegramError

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def update_users_from_telegram():
    """Получить информацию о пользователях из Telegram и обновить БД"""
    
    logger.info("🔄 Начинаем обновление информации о пользователях из Telegram...")
    
    # Создаем бота
    bot = Bot(token=Config.BOT_TOKEN)
    
    # Инициализируем базу данных
    await db.init()
    
    # Получаем всех пользователей без username
    async with db.manager.get_connection() as conn:
        cursor = await conn.execute("""
            SELECT DISTINCT user_id FROM users 
            WHERE username IS NULL OR username = ''
        """)
        users_without_username = await cursor.fetchall()
    
    logger.info(f"📊 Найдено {len(users_without_username)} пользователей без username в БД")
    
    # Также получаем user_id из метаданных WooCommerce купонов
    from utils.woocommerce import woo_manager
    
    if woo_manager.is_enabled():
        all_coupons = await woo_manager.get_all_bot_coupons(per_page=100)
        
        telegram_ids = set()
        for coupon in all_coupons:
            meta_data = coupon.get('meta_data', [])
            for meta in meta_data:
                if meta.get('key') == '_telegram_user_id':
                    telegram_ids.add(int(meta.get('value', 0)))
        
        logger.info(f"📊 Найдено {len(telegram_ids)} уникальных Telegram ID в купонах WooCommerce")
    else:
        telegram_ids = set()
    
    # Объединяем ID из БД и WooCommerce
    all_user_ids = set([user[0] for user in users_without_username]) | telegram_ids
    logger.info(f"📋 Всего уникальных user_id для обновления: {len(all_user_ids)}")
    
    updated_count = 0
    error_count = 0
    
    for user_id in all_user_ids:
        try:
            # Пытаемся получить информацию о пользователе
            chat = await bot.get_chat(user_id)
            
            username = chat.username
            first_name = chat.first_name
            last_name = chat.last_name
            
            if username:
                logger.info(f"✅ Получен username для {user_id}: @{username}")
                
                # Обновляем или создаем запись в БД
                await db.user.get_or_create_user(
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name
                )
                
                updated_count += 1
            else:
                logger.warning(f"⚠️  У пользователя {user_id} нет username")
        
        except TelegramError as e:
            if "chat not found" in str(e).lower() or "user not found" in str(e).lower():
                logger.warning(f"⚠️  Пользователь {user_id} не найден в Telegram")
            else:
                logger.error(f"❌ Ошибка получения информации о {user_id}: {e}")
            error_count += 1
        
        except Exception as e:
            logger.error(f"❌ Исключение при обработке {user_id}: {str(e)}")
            error_count += 1
        
        # Задержка, чтобы не превысить лимиты API
        await asyncio.sleep(0.1)
    
    logger.info(f"""
    
    📊 Обновление завершено:
    ✅ Успешно обновлено: {updated_count}
    ❌ Ошибок: {error_count}
    📋 Всего обработано: {len(all_user_ids)}
    """)


if __name__ == "__main__":
    asyncio.run(update_users_from_telegram())

