"""
Система уведомлений о скором истечении промокодов для PlummyPromo
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from telegram import Bot
from telegram.constants import ParseMode

from database.database import db
from utils.config import Config
from utils.woocommerce import woo_manager
from utils.media import media_manager

logger = logging.getLogger(__name__)


class PromoNotificationSystem:
    """Система уведомлений о скором истечении промокодов"""
    
    def __init__(self, bot: Bot):
        """
        Инициализация системы уведомлений
        
        Args:
            bot: Экземпляр Telegram Bot
        """
        self.bot = bot
        self.is_running = False
        self.check_interval = 3600  # Проверять каждый час (3600 секунд)
        
        # Настройки уведомлений (за сколько дней до истечения отправлять)
        self.notification_schedule = {
            5: {  # За 5 дней
                'text': """Ваш промокод истечет через 5 дней
Успейте заказать без комиссии!
<a href="http://plummy.ru/?utm_source=telegram&utm_medium=social&utm_campaign=bot">Plummy.ru</a>""",
                'field_sent': 'notification_5_days_sent',
                'field_date': 'notification_5_days_date'
            },
            3: {  # За 3 дня
                'text': """По промокоду мы гарантируем САМЫЕ НИЗКИЕ цены на оригинальные вещи.""",
                'field_sent': 'notification_3_days_sent', 
                'field_date': 'notification_3_days_date'
            },
            1: {  # За 1 день
                'text': """Ваш промокод истечет через 24 часа
Не упустите свой шанс!
<a href="http://plummy.ru/?utm_source=telegram&utm_medium=social&utm_campaign=bot">Plummy.ru</a>""",
                'field_sent': 'notification_1_day_sent',
                'field_date': 'notification_1_day_date'
            }
        }
        
        # Текст запроса обратной связи после истечения промокода
        self.feedback_request_text = """Мы видим, что вы не воспользовались промокодом.
Пожалуйста, дайте обратную связь, почему вы не сделали у нас заказ и мы постараемся стать лучше."""
        
        logger.info("📱 PromoNotificationSystem инициализирован")
    
    async def start_notifications(self):
        """Запустить систему уведомлений"""
        if self.is_running:
            logger.warning("⚠️ Система уведомлений уже запущена")
            return
        
        self.is_running = True
        logger.info("🚀 Запуск системы уведомлений о промокодах")
        
        # Запускаем фоновую задачу
        asyncio.create_task(self._notification_loop())
    
    async def stop_notifications(self):
        """Остановить систему уведомлений"""
        self.is_running = False
        logger.info("⏹️ Система уведомлений остановлена")
    
    async def _notification_loop(self):
        """Основной цикл проверки и отправки уведомлений"""
        logger.info(f"🔄 Запущен цикл уведомлений (интервал: {self.check_interval} сек)")
        
        while self.is_running:
            try:
                await self._check_and_send_notifications()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"❌ Ошибка в цикле уведомлений: {e}", exc_info=True)
                # При ошибке ждем немного и продолжаем
                await asyncio.sleep(60)
    
    async def _check_and_send_notifications(self):
        """Проверить все промокоды и отправить необходимые уведомления"""
        logger.info("🔍 Проверка промокодов для уведомлений...")
        
        try:
            # Получаем все активные (неиспользованные) промокоды
            active_promos = await self._get_active_promocodes()
            
            if not active_promos:
                logger.info("📭 Нет активных промокодов для проверки")
                return
            
            logger.info(f"📋 Найдено {len(active_promos)} активных промокодов")
            
            notifications_sent = 0
            
            for promo in active_promos:
                try:
                    # Дополнительная проверка синхронизации с WooCommerce
                    if not await self._validate_promo_before_notification(promo):
                        continue
                    
                    # Проверяем необходимость отправки уведомлений
                    sent_count = await self._process_promo_notifications(promo)
                    notifications_sent += sent_count
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка обработки промокода {promo.get('code', 'UNKNOWN')}: {e}")
                    continue
            
            # Проверяем истекшие промокоды для запроса обратной связи
            await self._check_and_send_feedback_requests()
            
            if notifications_sent > 0:
                logger.info(f"📤 Отправлено уведомлений: {notifications_sent}")
            else:
                logger.info("📭 Уведомления к отправке не найдены")
                
        except Exception as e:
            logger.error(f"❌ Ошибка проверки уведомлений: {e}", exc_info=True)
    
    async def _get_active_promocodes(self) -> List[Dict]:
        """Получить все активные промокоды"""
        try:
            async with db.manager.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT p.*, u.notifications_enabled, u.is_blocked
                    FROM promocodes p
                    JOIN users u ON p.user_id = u.user_id
                    WHERE p.is_used = 0 
                    AND u.notifications_enabled = 1 
                    AND u.is_blocked = 0
                    ORDER BY p.created_date ASC
                """)
                rows = await cursor.fetchall()
                
                # Преобразуем в список словарей
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения активных промокодов: {e}")
            return []
    
    async def _validate_promo_before_notification(self, promo: Dict) -> bool:
        """
        Валидировать промокод перед отправкой уведомления
        Проверяет синхронизацию с WooCommerce и актуальность
        """
        try:
            # Если WooCommerce интеграция включена, проверяем статус на сайте
            if Config.WOOCOMMERCE_ENABLED and woo_manager.is_enabled():
                try:
                    sync_result = await woo_manager.sync_coupon_status(
                        promo['code'], 
                        promo.get('woocommerce_id')
                    )
                    
                    if not sync_result.get('synced', False):
                        # Промокод не найден на сайте
                        error_msg = sync_result.get('error', '').lower()
                        if 'не найден' in error_msg or 'not found' in error_msg:
                            logger.info(f"🗑️ Промокод {promo['code']} удален с сайта, пропускаем уведомление")
                            # Помечаем как использованный в локальной базе
                            await db.promo.use_promo_code(promo['code'])
                            return False
                    
                    if sync_result.get('is_used', False):
                        # Промокод использован на сайте
                        logger.info(f"✅ Промокод {promo['code']} использован на сайте, пропускаем уведомление")
                        # Синхронизируем с локальной базой
                        await db.promo.use_promo_code(promo['code'])
                        return False
                        
                except Exception as e:
                    # Если WooCommerce недоступен, продолжаем с локальными данными
                    logger.warning(f"⚠️ Ошибка синхронизации с WooCommerce для {promo['code']}: {e}")
            
            # Дополнительная проверка - промокод все еще активен в локальной базе
            if promo['is_used']:
                logger.info(f"✅ Промокод {promo['code']} использован локально, пропускаем уведомление")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка валидации промокода {promo.get('code', 'UNKNOWN')}: {e}")
            return False
    
    async def _process_promo_notifications(self, promo: Dict) -> int:
        """
        Обработать уведомления для конкретного промокода
        
        Returns:
            Количество отправленных уведомлений
        """
        notifications_sent = 0
        
        try:
            # Рассчитываем дату истечения промокода
            created_date = datetime.strptime(promo['created_date'][:19], "%Y-%m-%d %H:%M:%S")
            duration_days = await db.settings.get_promo_duration_days()
            expiry_date = created_date + timedelta(days=duration_days)
            
            # Если промокод уже истек, пропускаем
            if datetime.now() >= expiry_date:
                logger.info(f"⏰ Промокод {promo['code']} истек, пропускаем уведомления")
                return 0
            
            # Проверяем каждый тип уведомления
            for days_before, notification_config in self.notification_schedule.items():
                notification_date = expiry_date - timedelta(days=days_before)
                
                # Время для отправки уведомления пришло?
                if datetime.now() >= notification_date:
                    # Проверяем, не отправляли ли уже это уведомление
                    if not promo[notification_config['field_sent']]:
                        # Отправляем уведомление
                        success = await self._send_notification(
                            promo,
                            notification_config,
                            expiry_date
                        )
                        
                        if success:
                            # Помечаем как отправленное
                            await self._mark_notification_sent(
                                promo['code'],
                                notification_config['field_sent'],
                                notification_config['field_date']
                            )
                            notifications_sent += 1
            
            return notifications_sent
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки уведомлений для {promo.get('code', 'UNKNOWN')}: {e}")
            return 0
    
    async def _send_notification(self, promo: Dict, config: Dict, expiry_date: datetime) -> bool:
        """
        Отправить уведомление пользователю
        
        Args:
            promo: Данные промокода
            config: Конфигурация уведомления
            expiry_date: Дата истечения промокода
            
        Returns:
            True если успешно отправлено
        """
        try:
            user_id = promo['user_id']
            promo_code = promo['code']
            
            # Формируем сообщение
            message_text = config['text']
            
            # Отправляем уведомление БЕЗ изображения (только текст)
            await self.bot.send_message(
                chat_id=user_id,
                text=message_text,
                parse_mode=ParseMode.HTML
            )
            
            logger.info(f"📤 Уведомление отправлено пользователю {user_id} для промокода {promo_code}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления: {e}")
            return False
    
    async def _mark_notification_sent(self, promo_code: str, sent_field: str, date_field: str):
        """Пометить уведомление как отправленное"""
        try:
            async with db.manager.get_connection() as conn:
                await conn.execute(f"""
                    UPDATE promocodes 
                    SET {sent_field} = 1, {date_field} = ?
                    WHERE code = ?
                """, (datetime.now().isoformat(), promo_code))
                await conn.commit()
                
        except Exception as e:
            logger.error(f"❌ Ошибка записи отправленного уведомления: {e}")
    
    async def get_notification_stats(self) -> Dict:
        """Получить статистику уведомлений"""
        try:
            async with db.manager.get_connection() as conn:
                # Статистика отправленных уведомлений
                cursor = await conn.execute("""
                    SELECT 
                        COUNT(*) as total_active_promos,
                        SUM(notification_5_days_sent) as notifications_5_days,
                        SUM(notification_3_days_sent) as notifications_3_days,
                        SUM(notification_1_day_sent) as notifications_1_day
                    FROM promocodes 
                    WHERE is_used = 0
                """)
                row = await cursor.fetchone()
                
                if row:
                    return {
                        'total_active_promos': row[0] or 0,
                        'notifications_5_days': row[1] or 0,
                        'notifications_3_days': row[2] or 0, 
                        'notifications_1_day': row[3] or 0,
                        'is_running': self.is_running
                    }
                else:
                    return {
                        'total_active_promos': 0,
                        'notifications_5_days': 0,
                        'notifications_3_days': 0,
                        'notifications_1_day': 0,
                        'is_running': self.is_running
                    }
                    
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики уведомлений: {e}")
            return {
                'error': str(e),
                'is_running': self.is_running
            }
    
    async def send_test_notification(self, user_id: int, notification_type: int) -> bool:
        """
        Отправить тестовое уведомление администратору
        
        Args:
            user_id: ID пользователя
            notification_type: Тип уведомления (5, 3 или 1)
            
        Returns:
            True если успешно отправлено
        """
        if notification_type not in self.notification_schedule:
            logger.error(f"❌ Неизвестный тип уведомления: {notification_type}")
            return False
        
        try:
            config = self.notification_schedule[notification_type]
            
            test_message = f"🧪 **ТЕСТОВОЕ УВЕДОМЛЕНИЕ** (за {notification_type} дн.)\n\n" + config['text']
            
            # Отправляем тестовое уведомление БЕЗ изображения (только текст)
            await self.bot.send_message(
                chat_id=user_id,
                text=test_message,
                parse_mode=ParseMode.HTML
            )
            
            logger.info(f"🧪 Тестовое уведомление (тип {notification_type}) отправлено пользователю {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки тестового уведомления: {e}")
            return False
    
    async def _check_and_send_feedback_requests(self):
        """Проверить истекшие промокоды и отправить запросы обратной связи"""
        logger.info("🔍 Проверка истекших промокодов для запроса обратной связи...")
        
        try:
            async with db.manager.get_connection() as conn:
                # Получаем промокоды, которые истекли и не были использованы
                # и для которых еще не запрашивалась обратная связь
                cursor = await conn.execute("""
                    SELECT p.*, u.notifications_enabled, u.is_blocked
                    FROM promocodes p
                    JOIN users u ON p.user_id = u.user_id
                    WHERE p.is_used = 0 
                    AND p.feedback_requested = 0
                    AND u.notifications_enabled = 1 
                    AND u.is_blocked = 0
                    ORDER BY p.created_date ASC
                """)
                rows = await cursor.fetchall()
                
                columns = [description[0] for description in cursor.description]
                expired_promos = [dict(zip(columns, row)) for row in rows]
                
                if not expired_promos:
                    logger.info("📭 Нет истекших промокодов для запроса обратной связи")
                    return
                
                logger.info(f"📋 Найдено {len(expired_promos)} истекших промокодов для проверки")
                
                feedback_requests_sent = 0
                
                for promo in expired_promos:
                    try:
                        # Проверяем, действительно ли промокод истек
                        created_date = datetime.strptime(promo['created_date'][:19], "%Y-%m-%d %H:%M:%S")
                        duration_days = await db.settings.get_promo_duration_days()
                        expiry_date = created_date + timedelta(days=duration_days)
                        
                        # Если промокод истек, отправляем запрос обратной связи
                        if datetime.now() > expiry_date:
                            success = await self._send_feedback_request(promo)
                            if success:
                                feedback_requests_sent += 1
                    
                    except Exception as e:
                        logger.error(f"❌ Ошибка обработки истекшего промокода {promo.get('code', 'UNKNOWN')}: {e}")
                        continue
                
                if feedback_requests_sent > 0:
                    logger.info(f"📤 Отправлено запросов обратной связи: {feedback_requests_sent}")
                    
        except Exception as e:
            logger.error(f"❌ Ошибка проверки истекших промокодов: {e}", exc_info=True)
    
    async def _send_feedback_request(self, promo: Dict) -> bool:
        """
        Отправить запрос обратной связи пользователю
        
        Args:
            promo: Данные промокода
            
        Returns:
            True если успешно отправлено
        """
        try:
            user_id = promo['user_id']
            promo_code = promo['code']
            
            # Отправляем запрос обратной связи
            await self.bot.send_message(
                chat_id=user_id,
                text=self.feedback_request_text,
                parse_mode=ParseMode.HTML
            )
            
            # Помечаем, что запрос обратной связи отправлен
            async with db.manager.get_connection() as conn:
                await conn.execute("""
                    UPDATE promocodes 
                    SET feedback_requested = 1, feedback_request_date = ?
                    WHERE code = ?
                """, (datetime.now().isoformat(), promo_code))
                await conn.commit()
            
            logger.info(f"📤 Запрос обратной связи отправлен пользователю {user_id} для промокода {promo_code}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки запроса обратной связи: {e}")
            return False


# Глобальный экземпляр системы уведомлений (будет инициализирован в main.py)
notification_system: Optional[PromoNotificationSystem] = None
