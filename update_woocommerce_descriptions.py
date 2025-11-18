"""
Скрипт для обновления описаний купонов в WooCommerce
Заменяет ID пользователей на их username
"""

import asyncio
import logging
from database.database import db
from utils.woocommerce import woo_manager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def update_all_coupon_descriptions():
    """Обновить описания всех купонов в WooCommerce"""
    
    if not woo_manager.is_enabled():
        logger.error("❌ WooCommerce интеграция отключена")
        return
    
    logger.info("🔄 Начинаем обновление описаний купонов в WooCommerce...")
    
    # Инициализируем базу данных
    await db.init()
    
    # Получаем ВСЕ купоны напрямую из WooCommerce
    logger.info("📥 Получаем все купоны из WooCommerce...")
    all_woo_coupons = await woo_manager.get_all_bot_coupons(per_page=100)
    
    if not all_woo_coupons:
        logger.info("ℹ️  Нет купонов в WooCommerce для обновления")
        return
    
    logger.info(f"📊 Найдено {len(all_woo_coupons)} купонов в WooCommerce")
    
    # Создаем словарь user_id -> username из БД для быстрого поиска
    async with db.manager.get_connection() as conn:
        cursor = await conn.execute("SELECT user_id, username FROM users WHERE username IS NOT NULL")
        users = await cursor.fetchall()
        user_mapping = {str(user_id): username for user_id, username in users}
    
    logger.info(f"📋 Загружено {len(user_mapping)} пользователей из БД")
    
    success_count = 0
    error_count = 0
    skipped_count = 0
    
    for coupon in all_woo_coupons:
        code = coupon.get('code', 'UNKNOWN')
        coupon_id = coupon.get('id')
        meta_data = coupon.get('meta_data', [])
        
        # Пытаемся получить username из метаданных WooCommerce
        username = None
        telegram_user_id = None
        
        for meta in meta_data:
            if meta.get('key') == '_telegram_username' and meta.get('value'):
                username = meta.get('value')
            if meta.get('key') == '_telegram_user_id':
                telegram_user_id = str(meta.get('value', ''))
        
        # Если username не найден в метаданных, ищем в БД по user_id
        if not username and telegram_user_id and telegram_user_id in user_mapping:
            username = user_mapping[telegram_user_id]
            logger.info(f"🔍 Username для купона {code} найден в БД: @{username}")
        
        # Если всё равно нет username, пропускаем
        if not username:
            logger.warning(f"⚠️  Для купона {code} (user_id: {telegram_user_id}) не найден username, пропускаем")
            skipped_count += 1
            continue
        
        logger.info(f"🔄 Обновляем купон {code} для @{username}...")
        
        try:
            result = await woo_manager.update_coupon_description(code, username)
            
            if result["success"]:
                success_count += 1
                logger.info(f"✅ Купон {code} обновлен")
            else:
                error_count += 1
                logger.error(f"❌ Ошибка обновления купона {code}: {result.get('error')}")
        
        except Exception as e:
            error_count += 1
            logger.error(f"❌ Исключение при обновлении купона {code}: {str(e)}")
        
        # Небольшая задержка между запросами, чтобы не перегружать API
        await asyncio.sleep(0.5)
    
    logger.info(f"""
    
    📊 Обновление завершено:
    ✅ Успешно обновлено: {success_count}
    ❌ Ошибок: {error_count}
    ⚠️  Пропущено (нет username): {skipped_count}
    📋 Всего обработано: {len(all_woo_coupons)}
    """)


if __name__ == "__main__":
    asyncio.run(update_all_coupon_descriptions())

