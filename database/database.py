"""
Основной модуль для работы с базой данных
"""

from .models import DatabaseManager, User, PromoCode, Analytics, Settings


class Database:
    """Главный класс для работы с базой данных"""
    
    def __init__(self, db_path: str = "bot_database.db"):
        self.manager = DatabaseManager(db_path)
        self.user = User(self.manager)
        self.promo = PromoCode(self.manager)
        self.analytics = Analytics(self.manager)
        self.settings = Settings(self.manager)
    
    async def init(self):
        """Инициализация базы данных"""
        await self.manager.init_database()


# Создаем экземпляр базы данных
db = Database()
