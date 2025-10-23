"""
Система мониторинга сайта с уведомлениями администратора
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from telegram import Bot
from telegram.constants import ParseMode

from .config import Config
from .uptimerobot import uptime_manager

logger = logging.getLogger(__name__)


class SiteMonitoring:
    """Система мониторинга сайта"""
    
    def __init__(self, bot: Bot):
        """
        Инициализация системы мониторинга
        
        Args:
            bot: Экземпляр Telegram бота
        """
        self.bot = bot
        self.admin_id = Config.ADMIN_ID
        self.check_interval = Config.UPTIMEROBOT_CHECK_INTERVAL
        self.monitoring_task = None
        self.is_monitoring = False
        self.notification_history = []  # История уведомлений
        self.last_notification_time = {}  # Время последнего уведомления для каждого монитора
        
    async def start_monitoring(self) -> bool:
        """
        Запустить мониторинг сайта
        
        Returns:
            True если мониторинг запущен успешно
        """
        if not uptime_manager.is_enabled():
            logger.error("❌ UptimeRobot не настроен, мониторинг не может быть запущен")
            return False
            
        if self.is_monitoring:
            logger.warning("⚠️ Мониторинг уже запущен")
            return True
            
        logger.info("🚀 Запуск системы мониторинга сайта...")
        
        # Тестируем подключение
        test_result = await uptime_manager.test_connection()
        if not test_result['success']:
            logger.error(f"❌ Ошибка подключения к UptimeRobot: {test_result.get('error')}")
            return False
            
        # Отправляем уведомление администратору о запуске мониторинга
        await self._send_admin_notification(
            "🚀 **Мониторинг сайта запущен**\n\n"
            f"✅ Подключение к UptimeRobot: активно\n"
            f"📊 Найдено мониторов: {test_result.get('monitors_count', 0)}\n"
            f"⏱ Интервал проверки: {self.check_interval} секунд\n\n"
            "Вы будете получать уведомления при изменении статуса сайта."
        )
        
        # Запускаем фоновую задачу мониторинга
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.is_monitoring = True
        
        logger.info("✅ Система мониторинга успешно запущена")
        return True
    
    async def stop_monitoring(self) -> bool:
        """
        Остановить мониторинг сайта
        
        Returns:
            True если мониторинг остановлен успешно
        """
        if not self.is_monitoring:
            logger.warning("⚠️ Мониторинг не запущен")
            return True
            
        logger.info("🛑 Остановка системы мониторинга...")
        
        self.is_monitoring = False
        
        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
                
        # Уведомляем администратора об остановке
        await self._send_admin_notification(
            "🛑 **Мониторинг сайта остановлен**\n\n"
            "Система мониторинга была отключена."
        )
        
        logger.info("✅ Система мониторинга остановлена")
        return True
        
    async def _monitoring_loop(self):
        """Основной цикл мониторинга"""
        logger.info("🔄 Запуск цикла мониторинга...")
        
        while self.is_monitoring:
            try:
                # Проверяем изменения статуса
                changes = await uptime_manager.check_for_status_changes()
                
                # Обрабатываем изменения
                for change in changes:
                    await self._handle_status_change(change)
                    
                # Ждем до следующей проверки
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                logger.info("🛑 Цикл мониторинга остановлен")
                break
            except Exception as e:
                logger.error(f"❌ Ошибка в цикле мониторинга: {str(e)}")
                # При ошибке ждем меньше, чтобы быстрее восстановиться
                await asyncio.sleep(min(30, self.check_interval))
    
    async def _handle_status_change(self, change: Dict[str, Any]):
        """
        Обработать изменение статуса монитора
        
        Args:
            change: Информация об изменении статуса
        """
        monitor_id = change['monitor_id']
        friendly_name = change['friendly_name']
        current_status = change['current_status']
        is_critical = change['is_critical']
        
        # Логируем изменение
        logger.info(
            f"🔄 Изменение статуса: {friendly_name} -> {current_status}"
        )
        
        # Проверяем, не отправляли ли мы уже уведомление недавно
        now = datetime.now()
        if monitor_id in self.last_notification_time:
            last_notification = self.last_notification_time[monitor_id]
            if now - last_notification < timedelta(minutes=5):
                logger.info(f"⏭ Пропускаем уведомление для {friendly_name} (недавно отправлено)")
                return
        
        # Формируем сообщение уведомления
        if current_status == 'DOWN':
            icon = "🔴"
            title = "САЙТ НЕДОСТУПЕН"
            urgency = "**КРИТИЧНО**"
        else:
            icon = "🟢"
            title = "САЙТ ВОССТАНОВЛЕН" 
            urgency = "**ВОССТАНОВЛЕНИЕ**"
            
        message = (
            f"{icon} **{title}**\n\n"
            f"{urgency}\n\n"
            f"📊 **Монитор:** {friendly_name}\n"
            f"🌐 **URL:** `{change['url']}`\n"
            f"📈 **Статус:** {change['status_description']}\n"
            f"🕐 **Время:** {change['change_time'].strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        
        if current_status == 'DOWN':
            message += "\n❗️ **Требуется внимание!** Проверьте работу сайта."
        else:
            message += "\n✅ **Сайт снова работает.** Проблема устранена."
            
        # Отправляем уведомление
        await self._send_admin_notification(message, urgent=is_critical)
        
        # Сохраняем в историю и обновляем время последнего уведомления
        self.notification_history.append({
            'timestamp': now,
            'monitor_id': monitor_id,
            'friendly_name': friendly_name,
            'status_change': change,
            'message': message
        })
        
        self.last_notification_time[monitor_id] = now
        
        # Ограничиваем размер истории (последние 100 записей)
        if len(self.notification_history) > 100:
            self.notification_history = self.notification_history[-100:]
    
    async def _send_admin_notification(self, message: str, urgent: bool = False):
        """
        Отправить уведомление администратору
        
        Args:
            message: Текст уведомления
            urgent: Является ли уведомление срочным
        """
        try:
            if urgent:
                # Для критичных уведомлений добавляем дополнительные элементы
                message = f"🚨 **СРОЧНО** 🚨\n\n{message}"
            
            await self.bot.send_message(
                chat_id=self.admin_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )
            
            logger.info(f"📨 Уведомление отправлено администратору {self.admin_id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления администратору: {str(e)}")
    
    async def get_monitoring_status(self) -> Dict[str, Any]:
        """
        Получить статус системы мониторинга
        
        Returns:
            Информация о состоянии мониторинга
        """
        if not uptime_manager.is_enabled():
            return {
                "enabled": False,
                "error": "UptimeRobot не настроен"
            }
            
        # Получаем статус мониторов
        monitors_status = await uptime_manager.get_monitor_status()
        
        return {
            "enabled": True,
            "is_monitoring": self.is_monitoring,
            "check_interval": self.check_interval,
            "admin_id": self.admin_id,
            "monitors": monitors_status.get('monitors', []) if monitors_status['success'] else [],
            "monitors_count": len(monitors_status.get('monitors', [])) if monitors_status['success'] else 0,
            "last_check": monitors_status.get('check_time') if monitors_status['success'] else None,
            "notification_count": len(self.notification_history),
            "api_status": "OK" if monitors_status['success'] else monitors_status.get('error', 'Неизвестная ошибка')
        }
    
    async def get_recent_notifications(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Получить последние уведомления
        
        Args:
            limit: Количество последних уведомлений
            
        Returns:
            Список последних уведомлений
        """
        return self.notification_history[-limit:] if self.notification_history else []
    
    def get_status_summary(self) -> str:
        """
        Получить краткую сводку состояния мониторинга
        
        Returns:
            Текстовая сводка
        """
        if not uptime_manager.is_enabled():
            return "❌ Мониторинг не настроен"
            
        if not self.is_monitoring:
            return "🛑 Мониторинг остановлен"
            
        return "🟢 Мониторинг активен"
        

# Глобальный экземпляр будет создан в main.py при запуске бота
site_monitoring = None
