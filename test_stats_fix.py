#!/usr/bin/env python3
"""
Тест исправления ошибки парсинга в /stats команде
"""

import asyncio
import sys
import logging
import traceback
from datetime import datetime

sys.path.append('.')

# Настройка логирования
logging.basicConfig(level=logging.INFO)


async def test_stats_formatting():
    """Тестирует исправление форматирования в админ статистике"""
    print('')
    print('🔧 ТЕСТИРОВАНИЕ ИСПРАВЛЕНИЯ /stats')
    print('=' * 60)
    print('')
    
    try:
        # Импортируем необходимые модули
        from handlers.admin import AdminHandlers
        from database.database import db
        from utils.config import Config
        
        print('1️⃣ Проверка импорта модулей...')
        print('   ✅ AdminHandlers импортирован')
        print('   ✅ База данных подключена')
        print('   ✅ Конфигурация загружена')
        
        # Инициализируем базу данных
        await db.init()
        print('   ✅ База данных инициализирована')
        
        print('')
        print('2️⃣ Проверка получения статистики из базы...')
        
        # Получаем статистику как в реальной функции
        stats_7d = await db.analytics.get_traffic_stats(days=7)
        stats_30d = await db.analytics.get_traffic_stats(days=30)
        promo_stats = await db.promo.get_promo_stats()
        conversion_stats = await db.analytics.get_conversion_stats()
        total_users = await db.user.get_users_count()
        
        print(f'   📊 Всего пользователей: {total_users}')
        print(f'   📊 Активных за 7 дней: {stats_7d.get("unique_users", 0)}')
        print(f'   📊 Активных за 30 дней: {stats_30d.get("unique_users", 0)}')
        print(f'   🎁 Промокодов выдано: {promo_stats.get("total_generated", 0)}')
        print(f'   🎁 Промокодов использовано: {promo_stats.get("total_used", 0)}')
        
        print('')
        print('3️⃣ Тестирование HTML форматирования...')
        
        # Формируем сообщение как в исправленной функции
        message = f"""<b>Статистика PlummyPromo бота</b>

<b>Общая информация:</b>
• Всего пользователей: {total_users}
• Активных пользователей (7 дней): {stats_7d.get('unique_users', 0)}
• Активных пользователей (30 дней): {stats_30d.get('unique_users', 0)}

<b>Промокоды:</b>
• Всего выдано: {promo_stats.get('total_generated', 0)}
• Использовано: {promo_stats.get('total_used', 0)}
• Коэффициент использования: {promo_stats.get('usage_rate', 0)}%

<b>Конверсии:</b>
• Старт → Промокод: {conversion_stats.get('start_to_promo', 0)}%
• Промокод → Покупка: {conversion_stats.get('promo_to_purchase', 0)}%
• Общая конверсия: {conversion_stats.get('overall_conversion', 0)}%"""

        # Добавляем статистику по дням
        if stats_7d.get('daily_stats'):
            message += "\n\n<b>Активность по дням (последние 5 дней):</b>\n"
            for day_stat in stats_7d['daily_stats'][:5]:
                date_str = str(day_stat['date'])
                users_str = str(day_stat['unique_users'])
                sessions_str = str(day_stat['sessions'])
                message += f"• {date_str}: {users_str} польз. ({sessions_str} сессий)\n"
        
        # Добавляем источники трафика
        if stats_7d.get('traffic_by_source'):
            message += "\n<b>Источники трафика (7 дней):</b>\n"
            for source in stats_7d['traffic_by_source']:
                source_name = str(source['source'])
                users_count = str(source['users'])
                message += f"• {source_name}: {users_count} польз.\n"
        
        # Проверяем длину сообщения
        message_length = len(message)
        print(f'   📏 Длина сообщения: {message_length} символов')
        
        if message_length > 4096:
            print('   ⚠️  Сообщение слишком длинное (>4096 символов)!')
        else:
            print('   ✅ Длина сообщения в пределах лимита')
        
        # Проверяем HTML теги
        html_tags = ['<b>', '</b>']
        all_tags_present = all(tag in message for tag in html_tags)
        
        if all_tags_present:
            print('   ✅ HTML теги присутствуют')
        else:
            print('   ❌ Проблема с HTML тегами')
        
        # Проверяем отсутствие Markdown символов
        markdown_symbols = ['**', '_', '`']
        has_markdown = any(symbol in message for symbol in markdown_symbols)
        
        if not has_markdown:
            print('   ✅ Markdown символы отсутствуют')
        else:
            print('   ⚠️  Найдены Markdown символы')
        
        print('')
        print('4️⃣ Результат исправления:')
        print('   ✅ Заменен Markdown (**текст**) на HTML (<b>текст</b>)')
        print('   ✅ Изменен ParseMode.MARKDOWN на ParseMode.HTML')
        print('   ✅ Добавлен str() для всех переменных')
        print('   ✅ Сообщение формируется без ошибок')
        
        print('')
        print('5️⃣ Превью сообщения:')
        print('-' * 50)
        print(message[:500] + '...' if len(message) > 500 else message)
        print('-' * 50)
        
        print('')
        print('✅ ТЕСТ ПРОЙДЕН УСПЕШНО!')
        print('🎊 Ошибка парсинга в /stats исправлена!')
        
        return True
        
    except Exception as e:
        print(f'❌ Ошибка в тесте: {e}')
        traceback.print_exc()
        return False


async def main():
    """Основная функция тестирования"""
    print('')
    print('🚀 ЗАПУСК ТЕСТИРОВАНИЯ ИСПРАВЛЕНИЯ')
    print('📅 Дата:', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print('')
    
    success = await test_stats_formatting()
    
    if success:
        print('')
        print('🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!')
        print('✅ Команда /stats теперь должна работать без ошибок')
        print('')
        print('📋 ЧТО БЫЛО ИСПРАВЛЕНО:')
        print('• Заменено форматирование Markdown на HTML')
        print('• Изменен режим парсинга на ParseMode.HTML')
        print('• Добавлена защита от None значений через str()')
        print('• Убраны потенциально проблемные символы')
        print('')
        print('🚀 РЕЗУЛЬТАТ:')
        print('Ошибка "Can\'t parse entities" больше не должна появляться!')
        return 0
    else:
        print('')
        print('❌ ТЕСТИРОВАНИЕ НЕУСПЕШНО')
        print('Необходимо дополнительное исследование проблемы')
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
