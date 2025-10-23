"""
Утилиты для аналитики и статистики
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
import io


class AnalyticsHelper:
    """Помощник для аналитики"""
    
    @staticmethod
    def parse_utm_params(start_param: str) -> Dict[str, str]:
        """
        Парсит UTM параметры из start команды
        
        Args:
            start_param: Параметр после /start
            
        Returns:
            Словарь с UTM параметрами
        """
        utm_data = {}
        
        if not start_param:
            return utm_data
        
        # Разбираем параметры вида: utm_source_medium_campaign
        parts = start_param.split('_')
        
        if len(parts) >= 1:
            utm_data['utm_source'] = parts[0]
        if len(parts) >= 2:
            utm_data['utm_medium'] = parts[1]
        if len(parts) >= 3:
            utm_data['utm_campaign'] = '_'.join(parts[2:])  # Остальное в campaign
            
        return utm_data
    
    @staticmethod
    def detect_referral_source(utm_data: Dict[str, str]) -> str:
        """
        Определяет источник трафика
        
        Args:
            utm_data: UTM параметры
            
        Returns:
            Название источника
        """
        source = utm_data.get('utm_source', '').lower()
        
        # Определяем тип источника
        social_sources = ['instagram', 'vk', 'facebook', 'telegram', 'tiktok', 'youtube']
        search_sources = ['google', 'yandex', 'bing']
        
        if source in social_sources:
            return f"social_{source}"
        elif source in search_sources:
            return f"search_{source}"
        elif source == 'email':
            return "email_campaign"
        elif source == 'sms':
            return "sms_campaign"
        elif source:
            return f"other_{source}"
        else:
            return "direct"
    
    @staticmethod
    def calculate_conversion_funnel(stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Рассчитывает воронку конверсии
        
        Args:
            stats: Статистика из базы данных
            
        Returns:
            Данные воронки конверсии
        """
        funnel_steps = [
            "Перешли в бота",
            "Запросили промокод", 
            "Использовали промокод"
        ]
        
        # Здесь должна быть логика расчета на основе данных из БД
        # Пока возвращаем заглушку
        return {
            "steps": funnel_steps,
            "values": [100, 75, 15],  # В процентах от первого шага
            "conversion_rates": [100, 75, 20]  # Процент перехода на каждом шаге
        }
    
    @staticmethod
    def format_stats_message(traffic_stats: Dict[str, Any], 
                           promo_stats: Dict[str, Any],
                           conversion_stats: Dict[str, Any]) -> str:
        """
        Форматирует статистику для отправки в сообщении
        
        Returns:
            Отформатированное сообщение со статистикой
        """
        message = "📊 **Статистика бота PlummyPromo**\n\n"
        
        # Статистика промокодов
        message += "🎁 **Промокоды:**\n"
        message += f"• Всего выдано: {promo_stats.get('total_generated', 0)}\n"
        message += f"• Использовано: {promo_stats.get('total_used', 0)}\n"
        message += f"• Процент использования: {promo_stats.get('usage_rate', 0)}%\n\n"
        
        # Конверсия
        message += "📈 **Конверсия:**\n"
        message += f"• Старт → Промокод: {conversion_stats.get('start_to_promo', 0)}%\n"
        message += f"• Промокод → Покупка: {conversion_stats.get('promo_to_purchase', 0)}%\n"
        message += f"• Общая конверсия: {conversion_stats.get('overall_conversion', 0)}%\n\n"
        
        # Источники трафика
        if traffic_stats.get('traffic_by_source'):
            message += "🚀 **Источники трафика:**\n"
            for source_data in traffic_stats['traffic_by_source']:
                source = source_data.get('source', 'unknown')
                users = source_data.get('users', 0)
                sessions = source_data.get('sessions', 0)
                message += f"• {source}: {users} польз. ({sessions} сессий)\n"
        
        return message
    
    @staticmethod
    def create_simple_chart_text(data: List[Tuple[str, int]], 
                                title: str) -> str:
        """
        Создает текстовую диаграмму (аналог графика)
        
        Args:
            data: Данные для диаграммы [(label, value), ...]
            title: Заголовок диаграммы
            
        Returns:
            Текстовое представление диаграммы
        """
        if not data:
            return f"📊 {title}\n\nНет данных для отображения"
        
        # Сортируем данные по убыванию значений
        sorted_data = sorted(data, key=lambda x: x[1], reverse=True)
        
        # Находим максимальное значение для масштабирования
        max_value = max(item[1] for item in sorted_data) if sorted_data else 1
        
        chart_text = f"📊 {title}\n\n"
        
        for label, value in sorted_data:
            # Создаем визуальную шкалу с символами ■
            bar_length = int((value / max_value) * 20) if max_value > 0 else 0
            bar = "■" * bar_length + "▫" * (20 - bar_length)
            
            chart_text += f"{label}: {value}\n{bar} {value}\n\n"
        
        return chart_text
