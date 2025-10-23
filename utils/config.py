"""
Конфигурация бота PlummyPromo
"""

import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()


class Config:
    """Класс конфигурации бота"""
    
    # Основные настройки бота
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
    # Список ID администраторов
    ADMIN_IDS = [int(os.getenv('ADMIN_ID', 0)), 6966354959]
    
    # База данных
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///bot_database.db')
    DB_PATH = DATABASE_URL.replace('sqlite:///', '') if DATABASE_URL.startswith('sqlite:///') else 'bot_database.db'
    
    # Настройки магазина
    SHOP_NAME = os.getenv('SHOP_NAME', 'PlummyPromo')
    SHOP_URL = os.getenv('SHOP_URL', 'https://your-shop.com')
    PROMO_DISCOUNT_PERCENT = int(os.getenv('PROMO_DISCOUNT_PERCENT', 10))
    
    # Настройки рассылок
    BROADCAST_ENABLED = os.getenv('BROADCAST_ENABLED', 'true').lower() == 'true'
    
    # WooCommerce API настройки
    WOOCOMMERCE_URL = os.getenv('WOOCOMMERCE_URL', '')  # URL магазина без слеша в конце
    WOOCOMMERCE_CONSUMER_KEY = os.getenv('WOOCOMMERCE_CONSUMER_KEY', '')
    WOOCOMMERCE_CONSUMER_SECRET = os.getenv('WOOCOMMERCE_CONSUMER_SECRET', '')
    WOOCOMMERCE_API_VERSION = os.getenv('WOOCOMMERCE_API_VERSION', 'wc/v3')
    WOOCOMMERCE_ENABLED = os.getenv('WOOCOMMERCE_ENABLED', 'true').lower() == 'true'
    
    # UptimeRobot API настройки
    UPTIMEROBOT_API_KEY = os.getenv('UPTIMEROBOT_API_KEY', '')  # Main API Key от UptimeRobot
    UPTIMEROBOT_ENABLED = os.getenv('UPTIMEROBOT_ENABLED', 'true').lower() == 'true'
    UPTIMEROBOT_CHECK_INTERVAL = int(os.getenv('UPTIMEROBOT_CHECK_INTERVAL', 60))  # Интервал проверки в секундах
    
    @classmethod
    def validate(cls):
        """Валидация конфигурации"""
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN не установлен в переменных окружения")
        
        if not cls.ADMIN_ID:
            raise ValueError("ADMIN_ID не установлен в переменных окружения")
        
        # Проверяем WooCommerce настройки, если интеграция включена
        if cls.WOOCOMMERCE_ENABLED:
            if not cls.WOOCOMMERCE_URL:
                raise ValueError("WOOCOMMERCE_URL не установлен, но интеграция включена")
            if not cls.WOOCOMMERCE_CONSUMER_KEY:
                raise ValueError("WOOCOMMERCE_CONSUMER_KEY не установлен")
            if not cls.WOOCOMMERCE_CONSUMER_SECRET:
                raise ValueError("WOOCOMMERCE_CONSUMER_SECRET не установлен")
            print("✅ WooCommerce интеграция настроена")
        else:
            print("ℹ️  WooCommerce интеграция отключена")
        
        print("✅ Конфигурация валидна")
        return True


# Проверяем наличие обязательных параметров при импорте
if __name__ == "__main__":
    try:
        Config.validate()
        print("Конфигурация успешно загружена")
    except ValueError as e:
        print(f"❌ Ошибка конфигурации: {e}")
        print("Убедитесь, что .env файл создан и заполнен по образцу .env.example")
