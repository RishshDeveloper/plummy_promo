"""
Утилита для работы с медиа файлами бота PlummyPromo
"""

import os
import logging
from pathlib import Path
from typing import Optional
from telegram import Bot, Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class MediaManager:
    """Менеджер для работы с медиа файлами"""
    
    def __init__(self):
        """Инициализация менеджера медиа"""
        # Определяем путь к медиа файлам относительно корня проекта
        self.project_root = Path(__file__).parent.parent
        self.media_path = self.project_root / "assets" / "media"
        
        # Маппинг событий на имена файлов
        self.image_mapping = {
            'hello': 'Hello.png',      # При первом запуске бота
            'promo': 'promo.png',      # Когда пользователь получил промокод  
            'done': 'done.png',        # Пользователь успешно применил промокод
            'finish': 'finish.png',    # Срок промокода истек
            'help': 'help.png'         # Нажал кнопку поддержка
        }
        
        logger.info(f"📁 MediaManager инициализирован, путь к медиа: {self.media_path}")
        self._validate_media_files()
    
    def _validate_media_files(self):
        """Проверить наличие всех медиа файлов"""
        missing_files = []
        
        for event, filename in self.image_mapping.items():
            file_path = self.media_path / filename
            if not file_path.exists():
                missing_files.append(f"{event}: {filename}")
                logger.error(f"❌ Медиа файл не найден: {file_path}")
            else:
                logger.info(f"✅ Медиа файл найден: {filename}")
        
        if missing_files:
            logger.warning(f"⚠️ Отсутствуют медиа файлы: {', '.join(missing_files)}")
        else:
            logger.info("✅ Все медиа файлы найдены")
    
    def get_media_path(self, event: str) -> Optional[Path]:
        """
        Получить путь к медиа файлу для события
        
        Args:
            event: Название события (hello, promo, done, finish, help, faq)
            
        Returns:
            Путь к файлу или None если файл не найден
        """
        if event not in self.image_mapping:
            logger.error(f"❌ Неизвестное событие: {event}")
            return None
        
        filename = self.image_mapping[event]
        file_path = self.media_path / filename
        
        if not file_path.exists():
            logger.error(f"❌ Файл не найден: {file_path}")
            return None
            
        return file_path
    
    async def send_photo_with_text(self, 
                                 update: Update, 
                                 event: str, 
                                 text: str,
                                 parse_mode: str = None,
                                 reply_markup = None) -> bool:
        """
        Отправить фото с текстом для определенного события
        
        Args:
            update: Update объект от Telegram
            event: Название события
            text: Текст сообщения
            parse_mode: Режим парсинга (Markdown, HTML)
            reply_markup: Клавиатура
            
        Returns:
            True если отправлено успешно, False в случае ошибки
        """
        try:
            photo_path = self.get_media_path(event)
            
            if not photo_path:
                # Если изображение не найдено, отправляем только текст
                logger.warning(f"⚠️ Изображение для события '{event}' не найдено, отправляем только текст")
                await update.message.reply_text(
                    text=text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
                return True
            
            # Отправляем фото с подписью
            with open(photo_path, 'rb') as photo_file:
                await update.message.reply_photo(
                    photo=photo_file,
                    caption=text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
                
            logger.info(f"📸 Отправлено изображение для события '{event}': {photo_path.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки изображения для события '{event}': {str(e)}")
            
            # В случае ошибки отправляем только текст
            try:
                await update.message.reply_text(
                    text=text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
                return True
            except Exception as text_error:
                logger.error(f"❌ Ошибка отправки текста: {str(text_error)}")
                return False
    
    async def send_photo_to_chat(self,
                               bot: Bot,
                               chat_id: int,
                               event: str,
                               text: str,
                               parse_mode: str = None,
                               reply_markup = None) -> bool:
        """
        Отправить фото с текстом в указанный чат (для уведомлений администратора)
        
        Args:
            bot: Bot объект
            chat_id: ID чата
            event: Название события
            text: Текст сообщения  
            parse_mode: Режим парсинга
            reply_markup: Клавиатура
            
        Returns:
            True если отправлено успешно
        """
        try:
            photo_path = self.get_media_path(event)
            
            if not photo_path:
                # Если изображение не найдено, отправляем только текст
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
                return True
            
            # Отправляем фото с подписью
            with open(photo_path, 'rb') as photo_file:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=photo_file,
                    caption=text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
                
            logger.info(f"📸 Отправлено изображение в чат {chat_id} для события '{event}'")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки изображения в чат {chat_id}: {str(e)}")
            
            # В случае ошибки отправляем только текст
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
                return True
            except Exception as text_error:
                logger.error(f"❌ Ошибка отправки текста в чат {chat_id}: {str(text_error)}")
                return False
    
    def list_available_media(self) -> dict:
        """
        Получить список доступных медиа файлов
        
        Returns:
            Словарь с информацией о файлах
        """
        media_info = {}
        
        for event, filename in self.image_mapping.items():
            file_path = self.media_path / filename
            media_info[event] = {
                'filename': filename,
                'path': str(file_path),
                'exists': file_path.exists(),
                'size': file_path.stat().st_size if file_path.exists() else 0
            }
        
        return media_info


# Создаем глобальный экземпляр менеджера медиа
media_manager = MediaManager()
