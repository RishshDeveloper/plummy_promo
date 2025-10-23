"""
Интеграция с UptimeRobot API для мониторинга доступности сайта
"""

import asyncio
import aiohttp
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum

from .config import Config

logger = logging.getLogger(__name__)


class MonitorStatus(Enum):
    """Статусы мониторов UptimeRobot"""
    PAUSED = 0          # Приостановлен
    NOT_CHECKED_YET = 1 # Еще не проверялся
    UP = 2              # Доступен
    SEEMS_DOWN = 8      # Кажется недоступным
    DOWN = 9            # Недоступен


class UptimeRobotManager:
    """Менеджер для работы с UptimeRobot API"""
    
    def __init__(self):
        """Инициализация менеджера UptimeRobot"""
        self.api_key = Config.UPTIMEROBOT_API_KEY
        self.base_url = "https://api.uptimerobot.com/v2"
        self.last_check_time = None
        self.cached_monitors = {}
        self.last_status_cache = {}  # Кэш для отслеживания изменений статуса
        
    def is_enabled(self) -> bool:
        """Проверить, включена ли интеграция с UptimeRobot"""
        return bool(self.api_key and len(self.api_key.strip()) > 0)
    
    async def get_monitors(self, logs: bool = False) -> Dict[str, Any]:
        """
        Получить список мониторов
        
        Args:
            logs: Получать ли логи (True для детальной информации)
            
        Returns:
            Данные о мониторах
        """
        if not self.is_enabled():
            return {
                "success": False,
                "error": "UptimeRobot API ключ не настроен"
            }
        
        try:
            payload = {
                'api_key': self.api_key,
                'format': 'json'
            }
            
            # Добавляем параметры логов только если они нужны
            if logs:
                payload.update({
                    'logs': '1',
                    'log_types': '1-2',  # 1-down, 2-up
                    'logs_limit': '10'
                })
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/getMonitors",
                    data=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('stat') == 'ok':
                            monitors = data.get('monitors', [])
                            logger.info(f"✅ Получено {len(monitors)} мониторов из UptimeRobot")
                            
                            # Кэшируем данные
                            self.cached_monitors = {
                                monitor['id']: monitor for monitor in monitors
                            }
                            self.last_check_time = datetime.now()
                            
                            return {
                                "success": True,
                                "monitors": monitors,
                                "count": len(monitors)
                            }
                        else:
                            error_msg = data.get('error', {}).get('message', 'Неизвестная ошибка API')
                            logger.error(f"❌ Ошибка UptimeRobot API: {error_msg}")
                            return {
                                "success": False,
                                "error": f"API ошибка: {error_msg}"
                            }
                    else:
                        logger.error(f"❌ HTTP ошибка UptimeRobot: {response.status}")
                        return {
                            "success": False,
                            "error": f"HTTP ошибка: {response.status}"
                        }
                        
        except asyncio.TimeoutError:
            logger.error("❌ Таймаут при запросе к UptimeRobot API")
            return {
                "success": False,
                "error": "Таймаут запроса к API"
            }
        except Exception as e:
            logger.error(f"❌ Исключение при запросе к UptimeRobot: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_monitor_status(self, monitor_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Получить статус конкретного монитора или всех мониторов
        
        Args:
            monitor_id: ID монитора (если None, то все мониторы)
            
        Returns:
            Статус мониторов
        """
        monitors_data = await self.get_monitors(logs=True)
        
        if not monitors_data['success']:
            return monitors_data
            
        monitors = monitors_data['monitors']
        
        if monitor_id:
            # Ищем конкретный монитор
            monitor = next((m for m in monitors if m['id'] == monitor_id), None)
            if not monitor:
                return {
                    "success": False,
                    "error": f"Монитор с ID {monitor_id} не найден"
                }
            monitors = [monitor]
        
        status_data = []
        for monitor in monitors:
            status_info = self._parse_monitor_status(monitor)
            status_data.append(status_info)
            
        return {
            "success": True,
            "monitors": status_data,
            "check_time": datetime.now().isoformat()
        }
    
    def _parse_monitor_status(self, monitor: Dict[str, Any]) -> Dict[str, Any]:
        """
        Парсить статус монитора
        
        Args:
            monitor: Данные монитора от API
            
        Returns:
            Обработанная информация о статусе
        """
        monitor_id = monitor.get('id')
        status_code = monitor.get('status', 0)
        status = MonitorStatus(status_code)
        
        # Базовая информация
        status_info = {
            'id': monitor_id,
            'friendly_name': monitor.get('friendly_name', 'Неизвестный'),
            'url': monitor.get('url', ''),
            'status_code': status_code,
            'status_name': status.name,
            'status_description': self._get_status_description(status),
            'is_up': status in [MonitorStatus.UP, MonitorStatus.NOT_CHECKED_YET],
            'is_down': status in [MonitorStatus.DOWN, MonitorStatus.SEEMS_DOWN],
            'uptime_ratio': monitor.get('all_time_uptime_ratio', '0'),
            'create_datetime': monitor.get('create_datetime', ''),
            'last_check_datetime': None,
            'down_since': None
        }
        
        # Парсим логи для дополнительной информации
        logs = monitor.get('logs', [])
        if logs:
            latest_log = logs[0]  # Последний лог
            status_info['last_check_datetime'] = latest_log.get('datetime', '')
            
            # Ищем информацию о времени недоступности
            for log in logs:
                if log.get('type') == 1:  # Down event
                    status_info['down_since'] = log.get('datetime', '')
                    break
        
        return status_info
    
    def _get_status_description(self, status: MonitorStatus) -> str:
        """Получить описание статуса на русском языке"""
        descriptions = {
            MonitorStatus.PAUSED: "Мониторинг приостановлен",
            MonitorStatus.NOT_CHECKED_YET: "Еще не проверялся",
            MonitorStatus.UP: "Сайт доступен",
            MonitorStatus.SEEMS_DOWN: "Сайт кажется недоступным",
            MonitorStatus.DOWN: "Сайт недоступен"
        }
        return descriptions.get(status, "Неизвестный статус")
    
    async def check_for_status_changes(self) -> List[Dict[str, Any]]:
        """
        Проверить изменения статуса мониторов с последней проверки
        
        Returns:
            Список изменений статуса
        """
        current_status = await self.get_monitor_status()
        
        if not current_status['success']:
            logger.error(f"Ошибка получения статуса мониторов: {current_status.get('error')}")
            return []
        
        changes = []
        current_monitors = current_status['monitors']
        
        for monitor in current_monitors:
            monitor_id = monitor['id']
            current_is_up = monitor['is_up']
            
            # Сравниваем с предыдущим статусом
            if monitor_id in self.last_status_cache:
                previous_is_up = self.last_status_cache[monitor_id]['is_up']
                
                # Проверяем изменения
                if previous_is_up != current_is_up:
                    change = {
                        'monitor_id': monitor_id,
                        'friendly_name': monitor['friendly_name'],
                        'url': monitor['url'],
                        'previous_status': 'UP' if previous_is_up else 'DOWN',
                        'current_status': 'UP' if current_is_up else 'DOWN',
                        'status_description': monitor['status_description'],
                        'change_time': datetime.now(),
                        'is_critical': not current_is_up  # Критично когда сайт падает
                    }
                    changes.append(change)
                    
                    logger.info(
                        f"🔄 Изменение статуса монитора {monitor['friendly_name']}: "
                        f"{'UP' if previous_is_up else 'DOWN'} → {'UP' if current_is_up else 'DOWN'}"
                    )
            
            # Обновляем кэш
            self.last_status_cache[monitor_id] = {
                'is_up': current_is_up,
                'last_update': datetime.now()
            }
        
        return changes
    
    async def test_connection(self) -> Dict[str, Any]:
        """
        Тестировать подключение к UptimeRobot API
        
        Returns:
            Результат тестирования
        """
        if not self.is_enabled():
            return {
                "success": False,
                "error": "UptimeRobot API ключ не настроен"
            }
        
        logger.info("🧪 Тестирование подключения к UptimeRobot API...")
        
        result = await self.get_monitors()
        
        if result['success']:
            monitors_count = result.get('count', 0)
            return {
                "success": True,
                "message": f"Подключение успешно! Найдено мониторов: {monitors_count}",
                "monitors_count": monitors_count,
                "api_working": True
            }
        else:
            return {
                "success": False,
                "error": result.get('error'),
                "api_working": False
            }


# Создаем экземпляр менеджера
uptime_manager = UptimeRobotManager()
