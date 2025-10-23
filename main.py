#!/usr/bin/env python3
"""
PlummyPromo Telegram Bot

Бот для продвижения интернет-магазина одежды с системой промокодов,
аналитикой и FAQ.

Автор: PlummyPromo Team
Версия: 1.0.0
"""

import asyncio
import logging
import os
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# Импортируем наши модули
from utils.config import Config
from database.database import db
from handlers.user import UserHandlers
from handlers.admin import AdminHandlers
from utils.monitoring import SiteMonitoring
from utils.notifications import PromoNotificationSystem, notification_system

# Health-check сервер для облачных платформ
try:
    from healthcheck import start_health_check_server
    HEALTHCHECK_ENABLED = True
except ImportError:
    HEALTHCHECK_ENABLED = False


# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PlummyPromoBot:
    """Основной класс бота PlummyPromo"""
    
    def __init__(self):
        self.application = None
    
    def _register_handlers(self):
        """Регистрация всех обработчиков команд"""
        app = self.application
        
        # === ПОЛЬЗОВАТЕЛЬСКИЕ КОМАНДЫ ===
        app.add_handler(CommandHandler("start", UserHandlers.start_command))
        app.add_handler(CommandHandler("help", UserHandlers.help_command))
        app.add_handler(CommandHandler("promo", UserHandlers.promo_command))
        app.add_handler(CommandHandler("faq", UserHandlers.faq_command))
        
        # === АДМИНСКИЕ КОМАНДЫ ===
        app.add_handler(CommandHandler("stats", AdminHandlers.admin_stats))
        app.add_handler(CommandHandler("admin_help", AdminHandlers.admin_help))
        
        # === CALLBACK QUERY HANDLERS ===
        # Админские callbacks
        app.add_handler(CallbackQueryHandler(
            AdminHandlers.handle_admin_callback,
            pattern=r"^admin_|^confirm_broadcast_"
        ))
        
        # Пользовательские callbacks  
        app.add_handler(CallbackQueryHandler(
            UserHandlers.handle_callback,
            pattern=r"^(faq_|get_promo|back_to_faq)"
        ))
        
        # === ОБРАБОТЧИКИ ТЕКСТОВЫХ СООБЩЕНИЙ ===
        # Админские текстовые сообщения (для рассылки)
        app.add_handler(MessageHandler(
            filters.TEXT & filters.User(Config.ADMIN_IDS),
            self._handle_admin_text
        ))
        
        # Обычные текстовые сообщения
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            UserHandlers.handle_text_messages
        ))
        
        # === ОБРАБОТЧИКИ ОШИБОК ===
        app.add_error_handler(self._error_handler)
        
        logger.info("✅ Все обработчики зарегистрированы")
    
    async def _handle_admin_text(self, update, context):
        """Обработчик текстовых сообщений от админа"""
        # Проверяем, ожидается ли сообщение для рассылки
        if context.user_data.get('awaiting_broadcast'):
            await AdminHandlers.admin_broadcast_message(update, context)
        # Проверяем, ожидается ли ввод настроек
        elif (context.user_data.get('waiting_for_discount') or 
              context.user_data.get('waiting_for_duration') or
              context.user_data.get('waiting_for_promo_code')):
            await AdminHandlers.handle_admin_text_input(update, context)
        else:
            # Обычное текстовое сообщение от админа
            await UserHandlers.handle_text_messages(update, context)
    
    async def _error_handler(self, update, context):
        """Обработчик ошибок"""
        logger.error(f"Update {update} caused error {context.error}")
        
        # Если есть update, отправляем сообщение об ошибке
        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "😔 Произошла ошибка при обработке вашего запроса. "
                    "Попробуйте позже или обратитесь в поддержку."
                )
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение об ошибке: {e}")


async def main():
    """Главная асинхронная функция"""
    try:
        logger.info("🚀 Запуск PlummyPromo Bot...")
        
        # Запуск health-check сервера для облачных платформ
        if HEALTHCHECK_ENABLED:
            try:
                port = int(os.getenv('PORT', 8080))
                start_health_check_server(port)
                logger.info(f"✅ Health-check сервер запущен на порту {port}")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось запустить health-check сервер: {e}")
        
        # Проверяем конфигурацию
        logger.info("🔧 Проверка конфигурации...")
        Config.validate()
        
        # Инициализируем базу данных
        await db.init()
        logger.info("✅ База данных инициализирована")
        
        # Создаем и настраиваем бота
        bot = PlummyPromoBot()
        bot.application = Application.builder().token(Config.BOT_TOKEN).build()
        bot._register_handlers()
        
        # Инициализируем систему мониторинга сайта
        from utils.monitoring import site_monitoring
        import utils.monitoring as monitoring_module
        monitoring_module.site_monitoring = SiteMonitoring(bot.application.bot)
        logger.info("✅ Система мониторинга инициализирована")
        
        # Инициализируем систему уведомлений о промокодах
        import utils.notifications as notifications_module
        notifications_module.notification_system = PromoNotificationSystem(bot.application.bot)
        logger.info("✅ Система уведомлений инициализирована")
        
        print("=" * 50)
        print(f"🎉 {Config.SHOP_NAME} Telegram Bot")  
        print("=" * 50)
        print("✅ Бот успешно запущен!")
        print(f"🏪 Магазин: {Config.SHOP_URL}")
        print(f"👨‍💼 Админ ID: {Config.ADMIN_ID}")
        print(f"💾 База данных: {Config.DB_PATH}")
        
        # Информация о мониторинге
        if Config.UPTIMEROBOT_ENABLED:
            print(f"📊 Мониторинг сайта: включен (интервал {Config.UPTIMEROBOT_CHECK_INTERVAL}с)")
        else:
            print("📊 Мониторинг сайта: отключен")
        
        # Запуск системы уведомлений о промокодах
        await notifications_module.notification_system.start_notifications()
        print("📱 Система уведомлений о промокодах: запущена")
        
        print("=" * 50)
        print("📋 Доступные команды:")
        print("👤 Для пользователей: /start, /help, /promo, /faq")
        print("👨‍💼 Для админа: /stats, /admin_help")
        print("=" * 50)
        print("🔄 Бот работает... (Ctrl+C для остановки)")
        print()
        
        # Запускаем бота
        logger.info("🚀 Запускаю PlummyPromo бота...")
        
        # Инициализируем приложение
        await bot.application.initialize()
        await bot.application.start()
        await bot.application.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=['message', 'callback_query']
        )
        
        # Ждем сигнала остановки
        try:
            # Простое ожидание
            while True:
                await asyncio.sleep(1)
        finally:
            # Останавливаем систему уведомлений
            if 'notifications_module' in locals() and notifications_module.notification_system:
                await notifications_module.notification_system.stop_notifications()
                logger.info("✅ Система уведомлений остановлена")
            
            # Корректно останавливаем бота
            await bot.application.updater.stop()
            await bot.application.stop()
            await bot.application.shutdown()
    
    except KeyboardInterrupt:
        logger.info("👋 Получен сигнал остановки от пользователя")
        print("\n👋 Бот остановлен!")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        raise


if __name__ == "__main__":
    # Проверяем Python версию
    import sys
    if sys.version_info < (3, 8):
        print("❌ Требуется Python 3.8 или выше")
        sys.exit(1)
    
    try:
        # Запускаем бота
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 До свидания!")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка запуска: {e}", exc_info=True)
        print(f"❌ Ошибка запуска: {e}")
        print("\n🔧 Проверьте:")
        print("1. Установлены ли переменные окружения (BOT_TOKEN, ADMIN_ID)")
        print("2. Установлены ли все зависимости")
        print("3. Правильный ли BOT_TOKEN")
        import traceback
        traceback.print_exc()
        sys.exit(1)
