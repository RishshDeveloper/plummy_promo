#!/usr/bin/env python3
"""
Скрипт для удаления всех промокодов из WooCommerce
Используйте этот скрипт если нужно очистить промокоды только на сайте
"""

import asyncio
import aiosqlite
from utils.config import Config
from utils.woocommerce import woo_manager

async def clear_woocommerce_coupons():
    """Удалить все промокоды из WooCommerce"""
    
    print("=" * 50)
    print("УДАЛЕНИЕ ПРОМОКОДОВ ИЗ WOOCOMMERCE")
    print("=" * 50)
    
    if not Config.WOOCOMMERCE_ENABLED:
        print("\n❌ WooCommerce интеграция отключена!")
        print("   Включите интеграцию в файле .env:")
        print("   WOOCOMMERCE_ENABLED=true")
        return False
    
    if not woo_manager.is_enabled():
        print("\n❌ WooCommerce менеджер не инициализирован!")
        print("   Проверьте настройки в файле .env")
        return False
    
    try:
        db_path = Config.DB_PATH
        
        async with aiosqlite.connect(db_path) as db:
            # Получаем все промокоды из локальной БД
            cursor = await db.execute("""
                SELECT code, woocommerce_synced, woocommerce_id 
                FROM promocodes 
                WHERE woocommerce_synced = 1
            """)
            synced_promos = await cursor.fetchall()
            
            if not synced_promos:
                print("\n📭 Нет синхронизированных промокодов в локальной БД")
                print("   Возможно промокоды уже удалены или не были синхронизированы")
                return True
            
            print(f"\n📋 Найдено синхронизированных промокодов: {len(synced_promos)}")
            print("\n🌐 Начинаю удаление промокодов из WooCommerce...")
            
            deleted_count = 0
            failed_count = 0
            
            for promo_code, is_synced, woo_id in synced_promos:
                try:
                    print(f"\n   Удаление: {promo_code} (WooCommerce ID: {woo_id})...")
                    success = await woo_manager.delete_coupon(promo_code)
                    
                    if success:
                        deleted_count += 1
                        print(f"   ✓ Удален: {promo_code}")
                    else:
                        failed_count += 1
                        print(f"   ✗ Не удалось удалить: {promo_code}")
                    
                    # Небольшая задержка между запросами
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    failed_count += 1
                    print(f"   ✗ Ошибка удаления {promo_code}: {e}")
            
            print("\n" + "=" * 50)
            print("РЕЗУЛЬТАТЫ УДАЛЕНИЯ")
            print("=" * 50)
            print(f"\n✅ Успешно удалено: {deleted_count}")
            if failed_count > 0:
                print(f"❌ Не удалось удалить: {failed_count}")
            print(f"\nℹ️  Всего обработано: {len(synced_promos)}")
            
            if deleted_count > 0:
                print("\n⚠️  ВАЖНО: Промокоды удалены только из WooCommerce!")
                print("   Они все еще остаются в локальной базе данных бота.")
                print("   Для полной очистки используйте: python3 clear_promo_data.py")
            
            return True
            
    except Exception as e:
        print(f"\n❌ Ошибка при удалении промокодов: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n⚠️  ВНИМАНИЕ! Этот скрипт удалит ВСЕ промокоды из WooCommerce (сайта)!")
    print("   - Будут удалены все синхронизированные промокоды с сайта")
    print("   - Промокоды останутся в локальной базе данных бота")
    print("   - Для полной очистки используйте: python3 clear_promo_data.py")
    
    confirm = input("\nПродолжить удаление? (введите 'ДА' для подтверждения): ")
    
    if confirm.strip().upper() == "ДА":
        asyncio.run(clear_woocommerce_coupons())
    else:
        print("\n❌ Операция отменена пользователем")

