"""
Интеграция с WooCommerce для автоматического создания промокодов
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import httpx
from woocommerce import API
import logging

from .config import Config

logger = logging.getLogger(__name__)


class WooCommerceManager:
    """Менеджер для работы с WooCommerce API"""
    
    def __init__(self):
        """Инициализация WooCommerce API клиента"""
        if not Config.WOOCOMMERCE_ENABLED:
            self.api = None
            return
            
        try:
            self.api = API(
                url=Config.WOOCOMMERCE_URL,
                consumer_key=Config.WOOCOMMERCE_CONSUMER_KEY,
                consumer_secret=Config.WOOCOMMERCE_CONSUMER_SECRET,
                version=Config.WOOCOMMERCE_API_VERSION,
                timeout=30
            )
            logger.info("✅ WooCommerce API клиент инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации WooCommerce API: {e}")
            self.api = None
    
    def is_enabled(self) -> bool:
        """Проверить, включена ли интеграция с WooCommerce"""
        return Config.WOOCOMMERCE_ENABLED and self.api is not None
    
    async def create_coupon(self, coupon_code: str, user_id: int, 
                           discount_percent: int = None, 
                           usage_limit: int = 1) -> Dict[str, Any]:
        """
        Создать купон в WooCommerce
        
        Args:
            coupon_code: Код купона
            user_id: ID пользователя Telegram
            discount_percent: Процент скидки
            usage_limit: Лимит использований
            
        Returns:
            Информация о созданном купоне
        """
        if not self.is_enabled():
            raise ValueError("WooCommerce интеграция отключена")
        
        discount_percent = discount_percent or Config.PROMO_DISCOUNT_PERCENT
        
        # Данные для создания купона
        coupon_data = {
            "code": coupon_code,
            "discount_type": "percent",  # Процентная скидка
            "amount": str(discount_percent),
            "description": f"Купон создан через Telegram бота для пользователя {user_id}",
            "usage_limit": usage_limit,
            "usage_limit_per_user": 1,
            "limit_usage_to_x_items": None,
            "free_shipping": False,
            "individual_use": True,  # Нельзя комбинировать с другими купонами
            "exclude_sale_items": False,  # Можно использовать на товары со скидкой
            "minimum_amount": "0.00",  # Минимальная сумма заказа
            "maximum_amount": "",  # Максимальная сумма заказа
            "date_expires": self._get_expiry_date(),  # Срок действия (30 дней)
            "email_restrictions": [],
            "meta_data": [
                {
                    "key": "_telegram_user_id",
                    "value": str(user_id)
                },
                {
                    "key": "_created_via_telegram_bot",
                    "value": "true"
                },
                {
                    "key": "_creation_date",
                    "value": datetime.now().isoformat()
                }
            ]
        }
        
        try:
            # Создаем купон через API (синхронно)
            response = await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: self.api.post("coupons", coupon_data)
            )
            
            if response.status_code == 201:
                coupon_info = response.json()
                logger.info(f"✅ Купон {coupon_code} создан в WooCommerce (ID: {coupon_info.get('id')})")
                
                return {
                    "success": True,
                    "woocommerce_id": coupon_info.get("id"),
                    "code": coupon_info.get("code"),
                    "discount_type": coupon_info.get("discount_type"),
                    "amount": coupon_info.get("amount"),
                    "date_created": coupon_info.get("date_created"),
                    "date_expires": coupon_info.get("date_expires"),
                    "usage_count": coupon_info.get("usage_count", 0),
                    "usage_limit": coupon_info.get("usage_limit"),
                    "description": coupon_info.get("description")
                }
            else:
                error_msg = f"Ошибка создания купона в WooCommerce: {response.status_code}"
                if hasattr(response, 'json'):
                    error_data = response.json()
                    if 'message' in error_data:
                        error_msg += f" - {error_data['message']}"
                
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "status_code": response.status_code
                }
                
        except Exception as e:
            error_msg = f"Исключение при создании купона в WooCommerce: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
    
    async def get_coupon_by_id(self, coupon_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить информацию о купоне из WooCommerce по ID
        
        Args:
            coupon_id: ID купона в WooCommerce
            
        Returns:
            Информация о купоне или None
        """
        if not self.is_enabled():
            return None
        
        try:
            # Получаем купон по ID
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.api.get(f"coupons/{coupon_id}")
            )
            
            if response.status_code == 200:
                coupon = response.json()
                return {
                    "id": coupon.get("id"),
                    "code": coupon.get("code"),
                    "discount_type": coupon.get("discount_type"),
                    "amount": coupon.get("amount"),
                    "usage_count": coupon.get("usage_count", 0),
                    "usage_limit": coupon.get("usage_limit"),
                    "date_expires": coupon.get("date_expires"),
                    "description": coupon.get("description")
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения купона ID {coupon_id}: {str(e)}")
            return None
    
    async def get_coupon(self, coupon_code: str) -> Optional[Dict[str, Any]]:
        """
        Получить информацию о купоне из WooCommerce
        
        Args:
            coupon_code: Код купона
            
        Returns:
            Информация о купоне или None
        """
        if not self.is_enabled():
            return None
        
        try:
            # Ищем купон по коду - правильная передача параметров
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.api.get("coupons", params={"code": coupon_code})
            )
            
            if response.status_code == 200:
                coupons = response.json()
                if coupons and len(coupons) > 0:
                    coupon = coupons[0]  # Берем первый найденный купон
                    return {
                        "id": coupon.get("id"),
                        "code": coupon.get("code"),
                        "discount_type": coupon.get("discount_type"),
                        "amount": coupon.get("amount"),
                        "usage_count": coupon.get("usage_count", 0),
                        "usage_limit": coupon.get("usage_limit"),
                        "date_expires": coupon.get("date_expires"),
                        "description": coupon.get("description")
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения купона {coupon_code}: {str(e)}")
            return None
    
    async def delete_coupon(self, coupon_code: str) -> bool:
        """
        Удалить купон из WooCommerce
        
        Args:
            coupon_code: Код купона
            
        Returns:
            True если удален успешно
        """
        if not self.is_enabled():
            return False
        
        try:
            # Сначала находим купон
            coupon_info = await self.get_coupon(coupon_code)
            if not coupon_info:
                logger.warning(f"Купон {coupon_code} не найден для удаления")
                return False
            
            # Удаляем купон
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.api.delete(f"coupons/{coupon_info['id']}", params={"force": True})
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Купон {coupon_code} удален из WooCommerce")
                return True
            else:
                logger.error(f"Ошибка удаления купона {coupon_code}: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Исключение при удалении купона {coupon_code}: {str(e)}")
            return False
    
    async def get_coupon_usage_stats(self, days: int = 30) -> Dict[str, Any]:
        """
        Получить статистику использования купонов
        
        Args:
            days: За сколько дней получить статистику
            
        Returns:
            Статистика купонов
        """
        if not self.is_enabled():
            return {"enabled": False}
        
        try:
            # Получаем все купоны, созданные ботом
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.api.get("coupons", params={
                    "per_page": 100,
                    "meta_key": "_created_via_telegram_bot",
                    "meta_value": "true"
                })
            )
            
            if response.status_code == 200:
                coupons = response.json()
                
                total_coupons = len(coupons)
                used_coupons = sum(1 for coupon in coupons if coupon.get('usage_count', 0) > 0)
                total_usage = sum(coupon.get('usage_count', 0) for coupon in coupons)
                
                return {
                    "enabled": True,
                    "total_coupons": total_coupons,
                    "used_coupons": used_coupons,
                    "total_usage": total_usage,
                    "usage_rate": round((used_coupons / total_coupons * 100) if total_coupons > 0 else 0, 2),
                    "avg_usage_per_coupon": round(total_usage / total_coupons if total_coupons > 0 else 0, 2)
                }
            else:
                logger.error(f"Ошибка получения статистики купонов: {response.status_code}")
                return {"enabled": True, "error": "Не удалось получить статистику"}
                
        except Exception as e:
            logger.error(f"Исключение при получении статистики купонов: {str(e)}")
            return {"enabled": True, "error": str(e)}
    
    def _get_expiry_date(self, days: int = 30) -> str:
        """
        Получить дату истечения купона
        
        Args:
            days: Через сколько дней истекает
            
        Returns:
            Дата в формате ISO
        """
        expiry_date = datetime.now() + timedelta(days=days)
        return expiry_date.strftime("%Y-%m-%dT%H:%M:%S")
    
    async def sync_coupon_status(self, coupon_code: str, woocommerce_id: int = None) -> Dict[str, Any]:
        """
        Синхронизировать статус использования промокода с WooCommerce
        
        Args:
            coupon_code: Код промокода для проверки
            woocommerce_id: ID промокода в WooCommerce (если известен)
            
        Returns:
            Информация о статусе промокода
        """
        if not self.is_enabled():
            return {
                "synced": False,
                "error": "WooCommerce интеграция отключена"
            }
        
        try:
            # Если есть ID, используем его для более быстрого поиска
            if woocommerce_id:
                logger.info(f"🔄 Синхронизация промокода {coupon_code} по ID: {woocommerce_id}")
                coupon_info = await self.get_coupon_by_id(woocommerce_id)
            else:
                logger.info(f"🔄 Синхронизация промокода {coupon_code} по коду")
                coupon_info = await self.get_coupon(coupon_code)
            
            if coupon_info:
                usage_count = coupon_info.get("usage_count", 0)
                is_used = usage_count > 0
                
                logger.info(f"🔄 Промокод {coupon_code}: использований в WooCommerce = {usage_count}")
                
                return {
                    "synced": True,
                    "is_used": is_used,
                    "usage_count": usage_count,
                    "coupon_info": coupon_info
                }
            else:
                logger.warning(f"⚠️ Промокод {coupon_code} не найден в WooCommerce")
                return {
                    "synced": False,
                    "error": "Промокод не найден в WooCommerce"
                }
                
        except Exception as e:
            logger.error(f"❌ Ошибка синхронизации промокода {coupon_code}: {str(e)}")
            return {
                "synced": False,
                "error": str(e)
            }
    
    async def test_connection(self) -> Dict[str, Any]:
        """
        Тестировать соединение с WooCommerce API
        
        Returns:
            Результат тестирования
        """
        if not self.is_enabled():
            return {
                "success": False,
                "error": "WooCommerce интеграция отключена"
            }
        
        try:
            # Пробуем получить информацию о системе
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.api.get("system_status")
            )
            
            if response.status_code == 200:
                system_info = response.json()
                return {
                    "success": True,
                    "store_info": {
                        "name": system_info.get("settings", {}).get("title", "Unknown"),
                        "version": system_info.get("environment", {}).get("version", "Unknown"),
                        "currency": system_info.get("settings", {}).get("currency", "Unknown")
                    }
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def mark_coupon_as_used(self, coupon_code: str) -> Dict[str, Any]:
        """
        Отметить купон как использованный в WooCommerce
        
        Args:
            coupon_code: Код купона для пометки как использованный
            
        Returns:
            Результат операции
        """
        if not self.is_enabled():
            return {
                "success": False,
                "error": "WooCommerce интеграция отключена"
            }
        
        try:
            # Сначала найдем купон
            coupon_info = await self.get_coupon(coupon_code)
            if not coupon_info:
                return {
                    "success": False,
                    "error": f"Купон {coupon_code} не найден"
                }
            
            coupon_id = coupon_info["id"]
            
            # Отмечаем купон как использованный через описание и статус
            current_usage = coupon_info.get('usage_count', 0)
            used_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            update_data = {
                "description": f"🔴 ИСПОЛЬЗОВАН АДМИНИСТРАТОРОМ ({current_usage + 1}/1) | Отмечен: {used_date}",
                "status": "private",  # Делаем купон приватным (неактивным для пользователей)
                "usage_limit": 1,    # Устанавливаем лимит 1  
                "usage_limit_per_user": 1,  # Лимит на пользователя 1
                "date_expires": used_date  # Устанавливаем дату истечения на текущее время
            }
            
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.api.put(f"coupons/{coupon_id}", update_data)
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Купон {coupon_code} отмечен как использованный в WooCommerce")
                return {
                    "success": True,
                    "message": f"Купон {coupon_code} отмечен как использованный"
                }
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_details = response.json()
                    if "message" in error_details:
                        error_msg = error_details["message"]
                except:
                    pass
                
                return {
                    "success": False,
                    "error": error_msg
                }
                
        except Exception as e:
            logger.error(f"Ошибка при отметке купона {coupon_code} как использованного: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_coupon_expiry_date(self, coupon_code: str) -> Optional[datetime]:
        """
        Получить реальную дату истечения промокода с сайта
        
        Args:
            coupon_code: Код промокода
            
        Returns:
            Дата истечения или None если не найдена
        """
        if not self.is_enabled():
            return None
        
        try:
            coupon_info = await self.get_coupon(coupon_code)
            if not coupon_info:
                return None
            
            date_expires = coupon_info.get('date_expires')
            if not date_expires:
                return None  # Промокод без ограничения по времени
            
            # Парсим дату истечения
            if 'T' in date_expires:
                # ISO формат: 2025-10-15T01:56:41
                expiry_date = datetime.fromisoformat(date_expires.replace('Z', '+00:00'))
                # Убираем timezone info для сравнения с локальным временем
                if expiry_date.tzinfo:
                    expiry_date = expiry_date.replace(tzinfo=None)
            else:
                # Простой формат даты: 2025-10-15
                expiry_date = datetime.strptime(date_expires, '%Y-%m-%d')
            
            return expiry_date
            
        except Exception as e:
            logger.error(f"Ошибка получения даты истечения промокода {coupon_code}: {str(e)}")
            return None


# Создаем экземпляр менеджера
woo_manager = WooCommerceManager()
