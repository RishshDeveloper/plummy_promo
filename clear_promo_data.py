#!/usr/bin/env python3
"""
Скрипт для очистки данных о промокодах всех пользователей
Удаляет промокоды как из локальной базы данных, так и из WooCommerce (сайта)
"""

import asyncio
import aiosqlite
from utils.config import Config
from utils.woocommerce import woo_manager

async def clear_promo_data():
    """Очистить данные о промокодах"""
    db_path = Config.DB_PATH
    
    print("=" * 50)
    print("ОЧИСТКА ДАННЫХ О ПРОМОКОДАХ")
    print("=" * 50)
    
    try:
        async with aiosqlite.connect(db_path) as db:
            # Получаем количество промокодов до удаления
            cursor = await db.execute("SELECT COUNT(*) FROM promocodes")
            total_promos = (await cursor.fetchone())[0]
            
            # Получаем количество пользователей
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            total_users = (await cursor.fetchone())[0]
            
            print(f"\n📊 Текущая статистика:")
            print(f"   Пользователей: {total_users}")
            print(f"   Промокодов в локальной БД: {total_promos}")
            
            # Получаем все промокоды для удаления из WooCommerce
            cursor = await db.execute("SELECT code, woocommerce_synced FROM promocodes")
            all_promos = await cursor.fetchall()
            
            # Удаляем промокоды из WooCommerce (сайта)
            if Config.WOOCOMMERCE_ENABLED and woo_manager.is_enabled():
                print(f"\n🌐 Удаление промокодов из WooCommerce (сайта)...")
                deleted_from_woo = 0
                failed_from_woo = 0
                
                for promo_code, is_synced in all_promos:
                    if is_synced:  # Удаляем только синхронизированные промокоды
                        try:
                            success = await woo_manager.delete_coupon(promo_code)
                            if success:
                                deleted_from_woo += 1
                                print(f"   ✓ Удален из WooCommerce: {promo_code}")
                            else:
                                failed_from_woo += 1
                                print(f"   ✗ Не удалось удалить из WooCommerce: {promo_code}")
                            
                            # Небольшая задержка между запросами
                            await asyncio.sleep(0.5)
                        except Exception as e:
                            failed_from_woo += 1
                            print(f"   ✗ Ошибка удаления {promo_code} из WooCommerce: {e}")
                
                print(f"\n   Удалено из WooCommerce: {deleted_from_woo}")
                if failed_from_woo > 0:
                    print(f"   ⚠️  Не удалось удалить из WooCommerce: {failed_from_woo}")
            else:
                print("\nℹ️  WooCommerce интеграция отключена - пропуск удаления с сайта")
            
            # Удаляем ВСЕ промокоды из локальной базы данных
            print("\n🗑️  Удаление всех промокодов из локальной БД...")
            await db.execute("DELETE FROM promocodes")
            
            # Обновляем настройки промокодов на новые значения (13%, 7 дней)
            print("⚙️  Обновление настроек промокодов...")
            await db.execute("""
                INSERT OR REPLACE INTO bot_settings (key, value, updated_date)
                VALUES ('promo_discount_percent', '13', datetime('now'))
            """)
            await db.execute("""
                INSERT OR REPLACE INTO bot_settings (key, value, updated_date)
                VALUES ('promo_duration_days', '7', datetime('now'))
            """)
            
            await db.commit()
            
            # Проверяем результат
            cursor = await db.execute("SELECT COUNT(*) FROM promocodes")
            remaining_promos = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            remaining_users = (await cursor.fetchone())[0]
            
            print("\n✅ Очистка завершена!")
            print(f"\n📊 Итоговая статистика:")
            print(f"   Пользователей: {remaining_users} (сохранено)")
            print(f"   Промокодов в локальной БД: {remaining_promos}")
            print(f"   Удалено промокодов из локальной БД: {total_promos}")
            print(f"\n⚙️  Новые настройки промокодов:")
            print(f"   Скидка: 13%")
            print(f"   Срок действия: 7 дней")
            print("\nℹ️  Примечание: Все пользователи (включая администраторов) могут получить новые промокоды")
            
    except Exception as e:
        print(f"\n❌ Ошибка при очистке данных: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 50)
    return True


if __name__ == "__main__":
    print("\n⚠️  ВНИМАНИЕ! Этот скрипт удалит ВСЕ данные о промокодах!")
    print("   - Будут удалены все промокоды всех пользователей")
    print("   - Данные о пользователях (регистрация, активность) сохранятся")
    print("   - Настройки промокодов обновятся до 13% и 7 дней")
    
    confirm = input("\nПродолжить? (введите 'ДА' для подтверждения): ")
    
    if confirm.strip().upper() == "ДА":
        asyncio.run(clear_promo_data())
    else:
        print("\n❌ Операция отменена пользователем")

