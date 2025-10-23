"""
Утилиты для работы с промокодами
"""

import uuid
import string
import random
from typing import List


class PromoCodeGenerator:
    """Генератор промокодов"""
    
    @staticmethod
    def generate_code(prefix: str = "PLUMMY", length: int = 6) -> str:
        """
        Генерирует уникальный промокод
        
        Args:
            prefix: Префикс промокода
            length: Длина случайной части
            
        Returns:
            Промокод в формате PREFIX + случайные символы
        """
        # Используем только буквы и цифры для удобства ввода
        chars = string.ascii_uppercase + string.digits
        random_part = ''.join(random.choices(chars, k=length))
        
        return f"{prefix}{random_part}"
    
    @staticmethod
    def generate_batch_codes(count: int, prefix: str = "PLUMMY", length: int = 6) -> List[str]:
        """
        Генерирует несколько промокодов
        
        Args:
            count: Количество промокодов
            prefix: Префикс промокода
            length: Длина случайной части
            
        Returns:
            Список промокодов
        """
        codes = []
        for _ in range(count):
            codes.append(PromoCodeGenerator.generate_code(prefix, length))
        
        return codes
    
    @staticmethod
    def is_valid_format(code: str, prefix: str = "PLUMMY") -> bool:
        """
        Проверяет корректность формата промокода
        
        Args:
            code: Промокод для проверки
            prefix: Ожидаемый префикс
            
        Returns:
            True если формат корректный
        """
        if not isinstance(code, str):
            return False
            
        if not code.startswith(prefix):
            return False
            
        # Проверяем что после префикса идут только буквы и цифры
        suffix = code[len(prefix):]
        return suffix.isalnum() and len(suffix) >= 4


class PromoCodeValidator:
    """Валидатор промокодов"""
    
    @staticmethod
    def validate_code_format(code: str) -> dict:
        """
        Валидирует формат промокода
        
        Returns:
            dict с результатом валидации
        """
        result = {
            "is_valid": False,
            "errors": []
        }
        
        if not code:
            result["errors"].append("Промокод не может быть пустым")
            return result
        
        if len(code) < 6:
            result["errors"].append("Промокод слишком короткий (минимум 6 символов)")
            return result
        
        if len(code) > 20:
            result["errors"].append("Промокод слишком длинный (максимум 20 символов)")
            return result
        
        if not code.replace('_', '').replace('-', '').isalnum():
            result["errors"].append("Промокод может содержать только буквы, цифры, '_' и '-'")
            return result
        
        result["is_valid"] = True
        return result
