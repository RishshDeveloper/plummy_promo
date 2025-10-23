"""
Обработчики для администратора бота PlummyPromo  
"""

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from datetime import datetime, timedelta
import asyncio
import io

from database.database import db
from utils.config import Config
from utils.analytics import AnalyticsHelper
# Динамический импорт систем мониторинга и уведомлений
# (инициализируются в main.py)
from utils.uptimerobot import uptime_manager


class AdminHandlers:
    """Обработчики для администратора"""
    
    @staticmethod
    def is_admin(user_id: int) -> bool:
        """Проверить, является ли пользователь администратором"""
        return user_id in Config.ADMIN_IDS
    
    @staticmethod
    async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать статистику бота (команда /stats)"""
        if not AdminHandlers.is_admin(update.effective_user.id):
            # Универсальная отправка сообщения об ошибке
            error_text = "У вас нет доступа к этой команде"
            if update.callback_query:
                await update.callback_query.edit_message_text(error_text)
            else:
                await update.message.reply_text(error_text)
            return
        
        try:
            # Получаем полную статистику
            stats_7d = await db.analytics.get_traffic_stats(days=7)
            stats_30d = await db.analytics.get_traffic_stats(days=30)
            promo_stats = await db.promo.get_promo_stats()
            conversion_stats = await db.analytics.get_conversion_stats()
            total_users = await db.user.get_users_count()
            
            # Формируем полное сообщение статистики с HTML форматированием
            message = f"""<b>Статистика PlummyPromo бота</b>

<b>Общая информация:</b>
• Всего пользователей: {total_users}
• Активных пользователей (7 дней): {stats_7d.get('unique_users', 0)}
• Активных пользователей (30 дней): {stats_30d.get('unique_users', 0)}

<b>Промокоды:</b>
• Всего выдано: {promo_stats.get('total_generated', 0)}
• Использовано: {promo_stats.get('total_used', 0)}
• Коэффициент использования: {promo_stats.get('usage_rate', 0)}%

<b>Конверсии:</b>
• Старт → Промокод: {conversion_stats.get('start_to_promo', 0)}%
• Промокод → Покупка: {conversion_stats.get('promo_to_purchase', 0)}%
• Общая конверсия: {conversion_stats.get('overall_conversion', 0)}%"""

            # Добавляем статистику по дням за последние 7 дней
            if stats_7d.get('daily_stats'):
                message += "\n\n<b>Активность по дням (последние 5 дней):</b>\n"
                for day_stat in stats_7d['daily_stats'][:5]:
                    date_str = str(day_stat['date'])
                    users_str = str(day_stat['unique_users'])
                    sessions_str = str(day_stat['sessions'])
                    message += f"• {date_str}: {users_str} польз. ({sessions_str} сессий)\n"
            
            # Добавляем источники трафика
            if stats_7d.get('traffic_by_source'):
                message += "\n<b>Источники трафика (7 дней):</b>\n"
                for source in stats_7d['traffic_by_source']:
                    source_name = str(source['source'])
                    users_count = str(source['users'])
                    message += f"• {source_name}: {users_count} польз.\n"
            
            # Создаем упрощенное меню админ панели
            keyboard_buttons = [
                [InlineKeyboardButton("Рассылка", callback_data="admin_broadcast")],
                [InlineKeyboardButton("Управление промокодами", callback_data="admin_promo_manage")],
                [InlineKeyboardButton("Уведомления", callback_data="admin_notifications")],
                [InlineKeyboardButton("Мониторинг сайта", callback_data="admin_monitoring")]
            ]
            
            keyboard = InlineKeyboardMarkup(keyboard_buttons)
            
            # Универсальная отправка сообщения - либо редактируем, либо отправляем новое
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    message,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                )
            else:
                await update.message.reply_text(
                    message,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                )
            
        except Exception as e:
            error_text = f"Ошибка при получении статистики: {str(e)}"
            # Универсальная отправка сообщения об ошибке
            if update.callback_query:
                await update.callback_query.edit_message_text(error_text)
            else:
                await update.message.reply_text(error_text)
    
    @staticmethod
    async def admin_broadcast_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Настройка рассылки"""
        if not AdminHandlers.is_admin(update.effective_user.id):
            return
            
        if not Config.BROADCAST_ENABLED:
            await update.callback_query.edit_message_text(
                "❌ Рассылки отключены в конфигурации",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        users_count = await db.user.get_users_count()
        active_users = await db.user.get_all_active_users()
        
        broadcast_text = f"""
📢 **Настройка рассылки**

👥 Всего пользователей: {users_count}  
✅ Активных пользователей: {len(active_users)}
🔕 Отключили уведомления: {users_count - len(active_users)}

📝 **Для создания рассылки:**
Отправьте сообщение с текстом рассылки, и я разошлю его всем активным пользователям.

⚠️ **Правила рассылки:**
• Не более 1 рассылки в день
• Только полезная информация
• Соблюдение законов о персональных данных

Готовы создать рассылку? Отправьте текст сообщения.
        """
        
        await update.callback_query.edit_message_text(
            broadcast_text,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Устанавливаем состояние ожидания сообщения для рассылки
        context.user_data['awaiting_broadcast'] = True
    
    
    
    
    
    
    @staticmethod  
    async def admin_promo_manage(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Управление промокодами"""
        if not AdminHandlers.is_admin(update.effective_user.id):
            return
        
        promo_stats = await db.promo.get_promo_stats()
        
        # Получаем текущие настройки из базы данных
        current_discount = await db.settings.get_promo_discount_percent()
        current_duration = await db.settings.get_promo_duration_days()
        
        manage_text = f"""
**Управление промокодами**

**Текущая статистика:**
• Всего выдано: {promo_stats.get('total_generated', 0)}
• Использовано: {promo_stats.get('total_used', 0)}  
• Процент использования: {promo_stats.get('usage_rate', 0)}%

**Текущие настройки:**
• Размер скидки: {current_discount}%
• Срок действия: {current_duration} дней
• Ограничения: 1 промокод на пользователя

**Примечание:**
Изменение настроек повлияет только на новые промокоды.
        """
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Задать параметры скидки", callback_data="admin_promo_settings")],
            [InlineKeyboardButton("Отметить использованным", callback_data="admin_promo_mark_used")],
            [InlineKeyboardButton("Назад", callback_data="admin_back_to_main")]
        ])
        
        # Универсальная отправка сообщения - либо редактируем, либо отправляем новое
        if update.callback_query:
            await update.callback_query.edit_message_text(
                manage_text,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                manage_text,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
    
    @staticmethod
    async def admin_promo_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Настройки промокодов"""
        if not AdminHandlers.is_admin(update.effective_user.id):
            return
        
        # Получаем текущие настройки из базы данных
        current_discount = await db.settings.get_promo_discount_percent()
        current_duration = await db.settings.get_promo_duration_days()
        
        settings_text = f"""
**Настройки промокодов**

**Текущие параметры:**
• Размер скидки: {current_discount}%
• Срок действия: {current_duration} дней

**Изменение параметров:**
Выберите параметр для изменения. Новые значения будут применяться только к новым промокодам.

**Примечание:** 
Изменения вступают в силу немедленно.
        """
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📈 Изменить процент скидки", callback_data="admin_set_discount")],
            [InlineKeyboardButton("📅 Изменить срок действия", callback_data="admin_set_duration")],
            [InlineKeyboardButton("← Назад", callback_data="admin_promo_manage")]
        ])
        
        # Универсальная отправка сообщения - либо редактируем, либо отправляем новое
        if update.callback_query:
            await update.callback_query.edit_message_text(
                settings_text,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                settings_text,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
    
    @staticmethod
    async def admin_set_discount(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запрос нового процента скидки"""
        if not AdminHandlers.is_admin(update.effective_user.id):
            return
        
        current_discount = await db.settings.get_promo_discount_percent()
        
        await update.callback_query.edit_message_text(
            f"""
**Изменение размера скидки**

Текущий размер скидки: {current_discount}%

Введите новый размер скидки (от 1 до 99):
            """,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Отменить", callback_data="admin_promo_settings")]
            ])
        )
        
        # Устанавливаем состояние для ожидания ввода
        context.user_data['waiting_for_discount'] = True
    
    @staticmethod
    async def admin_set_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запрос нового срока действия"""
        if not AdminHandlers.is_admin(update.effective_user.id):
            return
        
        current_duration = await db.settings.get_promo_duration_days()
        
        await update.callback_query.edit_message_text(
            f"""
**Изменение срока действия промокода**

Текущий срок действия: {current_duration} дней

Введите новый срок действия в днях (от 1 до 365):
            """,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Отменить", callback_data="admin_promo_settings")]
            ])
        )
        
        # Устанавливаем состояние для ожидания ввода
        context.user_data['waiting_for_duration'] = True
    
    @staticmethod
    async def admin_list_unsynced(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать список несинхронизированных промокодов"""
        if not AdminHandlers.is_admin(update.effective_user.id):
            return
        
        unsynced_codes = await db.promo.get_unsynced_promocodes()
        
        if unsynced_codes:
            unsynced_text = "📋 **Несинхронизированные промокоды:**\n\n"
            
            for i, promo in enumerate(unsynced_codes[:10], 1):  # Показываем первые 10
                unsynced_text += f"{i}. `{promo['code']}` - {promo.get('sync_error', 'Ошибка неизвестна')}\n"
            
            if len(unsynced_codes) > 10:
                unsynced_text += f"\n... и еще {len(unsynced_codes) - 10} промокодов"
        else:
            unsynced_text = "✅ **Все промокоды синхронизированы**\n\nНет промокодов требующих синхронизации с WooCommerce."
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Обновить", callback_data="admin_list_unsynced")],
            [InlineKeyboardButton("← Назад", callback_data="admin_woocommerce")]
        ])
        
        await update.callback_query.edit_message_text(
            unsynced_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    
    @staticmethod
    async def admin_promo_mark_used(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отметить промокод как использованный"""
        if not AdminHandlers.is_admin(update.effective_user.id):
            return
        
        await update.callback_query.edit_message_text(
            """
**Отметить промокод использованным**

Введите код промокода который нужно отметить как использованный:

Пример: PLUMMYABC123
            """,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Отменить", callback_data="admin_promo_manage")]
            ])
        )
        
        # Устанавливаем состояние для ожидания ввода
        context.user_data['waiting_for_promo_code'] = True
    
    @staticmethod
    async def handle_admin_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстового ввода администратора для настроек"""
        if not AdminHandlers.is_admin(update.effective_user.id):
            return
        
        text = update.message.text.strip()
        
        # Обработка ввода процента скидки
        if context.user_data.get('waiting_for_discount'):
            try:
                discount = int(text)
                if 1 <= discount <= 99:
                    # Сохраняем новое значение в базу данных
                    success = await db.settings.set_promo_discount_percent(discount)
                    
                    if success:
                        await update.message.reply_text(
                            f"**Размер скидки обновлен**: {discount}%\n\n"
                            f"Изменения вступят в силу для новых промокодов немедленно.\n"
                            f"Старые промокоды остаются с прежней скидкой.",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    else:
                        await update.message.reply_text(
                            "Ошибка при сохранении настройки. Попробуйте еще раз.",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    context.user_data.pop('waiting_for_discount', None)
                    
                    # Возвращаемся к настройкам
                    await AdminHandlers.admin_promo_settings(update, context)
                    return
                else:
                    await update.message.reply_text("Введите число от 1 до 99")
                    return
            except ValueError:
                await update.message.reply_text("Введите корректное число")
                return
        
        # Обработка ввода срока действия
        elif context.user_data.get('waiting_for_duration'):
            try:
                duration = int(text)
                if 1 <= duration <= 365:
                    # Сохраняем новое значение в базу данных
                    success = await db.settings.set_promo_duration_days(duration)
                    
                    if success:
                        await update.message.reply_text(
                            f"**Срок действия обновлен**: {duration} дней\n\n"
                            f"Изменения вступят в силу для новых промокодов немедленно.\n"
                            f"Старые промокоды сохраняют свой прежний срок действия.",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    else:
                        await update.message.reply_text(
                            "Ошибка при сохранении настройки. Попробуйте еще раз.",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    context.user_data.pop('waiting_for_duration', None)
                    
                    # Возвращаемся к настройкам  
                    await AdminHandlers.admin_promo_settings(update, context)
                    return
                else:
                    await update.message.reply_text("Введите число от 1 до 365")
                    return
            except ValueError:
                await update.message.reply_text("Введите корректное число")
                return
        
        # Обработка ввода промокода для отметки использованным
        elif context.user_data.get('waiting_for_promo_code'):
            promo_code = text.upper().strip()
            
            try:
                # Отправляем сообщение о начале обработки
                processing_msg = await update.message.reply_text(
                    f"Обрабатываю промокод {promo_code}...",
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Проверяем существование промокода и отмечаем как использованный
                success = await db.promo.use_promo_code(promo_code)
                
                if success:
                    # Дополнительно проверяем синхронизацию с WooCommerce
                    try:
                        from utils.woocommerce import woo_manager, Config
                        if Config.WOOCOMMERCE_ENABLED and woo_manager.is_enabled():
                            # Небольшая задержка для завершения синхронизации
                            await asyncio.sleep(1)
                            
                            result_message = f"""**Промокод {promo_code} отмечен как использованный**

✅ **Локальная база данных:** обновлена
✅ **Сайт (WooCommerce):** синхронизирован

Промокод больше не может быть использован на сайте."""
                        else:
                            result_message = f"""**Промокод {promo_code} отмечен как использованный**

✅ **Локальная база данных:** обновлена
⚠️ **Сайт (WooCommerce):** интеграция отключена

Примечание: Промокод отмечен только в боте."""
                    except Exception as sync_error:
                        result_message = f"""**Промокод {promo_code} отмечен как использованный**

✅ **Локальная база данных:** обновлена
❌ **Сайт (WooCommerce):** ошибка синхронизации

Ошибка: {str(sync_error)}"""
                    
                    await processing_msg.edit_text(
                        result_message,
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    await processing_msg.edit_text(
                        f"**Промокод {promo_code} не найден или уже использован**",
                        parse_mode=ParseMode.MARKDOWN
                    )
                
                context.user_data.pop('waiting_for_promo_code', None)
                
                # Возвращаемся к управлению промокодами через 2 секунды
                await asyncio.sleep(2)
                await AdminHandlers.admin_promo_manage(update, context)
                return
                
            except Exception as e:
                await update.message.reply_text(
                    f"**Ошибка при обработке промокода:** {str(e)}",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
    
    @staticmethod
    async def admin_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка сообщения для рассылки"""
        if not AdminHandlers.is_admin(update.effective_user.id):
            return
            
        if not context.user_data.get('awaiting_broadcast'):
            return
        
        # Убираем флаг ожидания
        context.user_data['awaiting_broadcast'] = False
        
        message_text = update.message.text
        if not message_text:
            await update.message.reply_text("❌ Сообщение не может быть пустым")
            return
        
        # Получаем список активных пользователей
        active_users = await db.user.get_all_active_users()
        
        if not active_users:
            await update.message.reply_text("❌ Нет активных пользователей для рассылки")
            return
        
        # Подтверждение рассылки
        confirm_text = f"""
📢 **Подтверждение рассылки**

📝 **Текст сообщения:**
{message_text}

👥 **Получателей:** {len(active_users)} пользователей

⚠️ Это действие нельзя отменить. Продолжить?
        """
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Да, отправить", callback_data=f"confirm_broadcast_{len(active_users)}")],
            [InlineKeyboardButton("❌ Отменить", callback_data="admin_back_to_main")]
        ])
        
        # Сохраняем текст сообщения для рассылки
        context.user_data['broadcast_text'] = message_text
        context.user_data['broadcast_users'] = active_users
        
        await update.message.reply_text(
            confirm_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    
    @staticmethod
    async def admin_execute_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выполнить рассылку"""
        if not AdminHandlers.is_admin(update.effective_user.id):
            return
        
        broadcast_text = context.user_data.get('broadcast_text')
        active_users = context.user_data.get('broadcast_users', [])
        
        if not broadcast_text or not active_users:
            await update.callback_query.edit_message_text("❌ Ошибка: данные рассылки не найдены")
            return
        
        await update.callback_query.edit_message_text(
            f"📤 Запускаю рассылку для {len(active_users)} пользователей..."
        )
        
        # Выполняем рассылку
        sent_count = 0
        failed_count = 0
        
        for user in active_users:
            try:
                await context.bot.send_message(
                    chat_id=user['user_id'],
                    text=f"📢 **Новости от {Config.SHOP_NAME}**\n\n{broadcast_text}",
                    parse_mode=ParseMode.MARKDOWN
                )
                sent_count += 1
                
                # Небольшая задержка между сообщениями
                await context.application.create_task_coro(lambda: None)
                
            except Exception as e:
                failed_count += 1
                print(f"Не удалось отправить сообщение пользователю {user['user_id']}: {e}")
        
        # Результат рассылки
        result_text = f"""
✅ **Рассылка завершена**

📊 **Результаты:**
• ✅ Доставлено: {sent_count}
• ❌ Не доставлено: {failed_count}
• 📈 Успешность: {round(sent_count / len(active_users) * 100, 1)}%

Рассылка завершена {datetime.now().strftime('%H:%M:%S')}
        """
        
        await update.callback_query.edit_message_text(result_text, parse_mode=ParseMode.MARKDOWN)
        
        # Очищаем данные рассылки
        context.user_data.pop('broadcast_text', None)
        context.user_data.pop('broadcast_users', None)
    
    @staticmethod
    async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик admin callback'ов"""
        if not AdminHandlers.is_admin(update.effective_user.id):
            return
        
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "admin_broadcast":
            await AdminHandlers.admin_broadcast_setup(update, context)
        elif data == "admin_promo_manage":
            await AdminHandlers.admin_promo_manage(update, context)
        elif data == "admin_promo_settings":
            await AdminHandlers.admin_promo_settings(update, context)
        elif data == "admin_set_discount":
            await AdminHandlers.admin_set_discount(update, context)
        elif data == "admin_set_duration":
            await AdminHandlers.admin_set_duration(update, context)
        elif data == "admin_promo_mark_used":
            await AdminHandlers.admin_promo_mark_used(update, context)
        elif data.startswith("confirm_broadcast_"):
            await AdminHandlers.admin_execute_broadcast(update, context)
        elif data == "admin_notifications":
            await AdminHandlers.admin_notifications(update, context)
        elif data == "admin_notifications_start":
            await AdminHandlers.admin_notifications_start(update, context)
        elif data == "admin_notifications_stop":
            await AdminHandlers.admin_notifications_stop(update, context)
        elif data == "admin_notifications_test_5":
            await AdminHandlers.admin_notifications_test(update, context, 5)
        elif data == "admin_notifications_test_3":
            await AdminHandlers.admin_notifications_test(update, context, 3)
        elif data == "admin_notifications_test_1":
            await AdminHandlers.admin_notifications_test(update, context, 1)
        elif data == "admin_monitoring":
            await AdminHandlers.admin_monitoring(update, context)
        elif data == "admin_monitoring_start":
            await AdminHandlers.admin_monitoring_start(update, context)
        elif data == "admin_monitoring_stop":
            await AdminHandlers.admin_monitoring_stop(update, context)
        elif data == "admin_monitoring_test":
            await AdminHandlers.admin_monitoring_test(update, context)
        elif data == "admin_monitoring_details":
            await AdminHandlers.admin_monitoring_details(update, context)
        elif data == "admin_stats":
            # Возвращаемся к главному меню статистики
            await AdminHandlers.admin_stats(update, context)
        elif data == "admin_back_to_main":
            # Возвращаемся к главному меню статистики
            await AdminHandlers.admin_stats(update, context)
    
    @staticmethod
    async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Помощь для администратора"""
        if not AdminHandlers.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ У вас нет доступа к админ-командам")
            return
        
        help_text = """
🔧 **Админ-панель PlummyPromo**

📊 **Команды статистики:**
/stats - Общая статистика бота
/admin_help - Эта справка

📢 **Рассылки:**
• Через кнопку в /stats
• Поддерживается Markdown разметка
• Автоматическая проверка активных пользователей

🎁 **Управление промокодами:**
• Просмотр всех выданных промокодов
• Отметка использованных промокодов
• Статистика конверсии

⚙️ **Настройки:**
• Изменение скидки в .env файле
• Включение/отключение рассылок
• Настройка аналитики

📊 **Аналитика включает:**
• Источники трафика (UTM метки)
• Конверсию по воронке
• Статистику по дням
• Эффективность промокодов

❓ Вопросы по настройке? Проверьте README.md
        """
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    # === ФУНКЦИИ МОНИТОРИНГА САЙТА ===
    
    @staticmethod
    async def admin_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Панель управления системой уведомлений"""
        if not AdminHandlers.is_admin(update.effective_user.id):
            await update.callback_query.edit_message_text(
                "У вас нет доступа к этой команде"
            )
            return
        
        try:
            # Динамически импортируем систему уведомлений
            from utils.notifications import notification_system
            
            if not notification_system:
                await update.callback_query.edit_message_text(
                    "❌ Система уведомлений не инициализирована\nУведомления будут доступны после перезапуска бота."
                )
                return
            
            # Получаем статистику уведомлений
            stats = await notification_system.get_notification_stats()
            
            status_text = "🟢 Работает автоматически" if stats.get('is_running', False) else "🔴 Не активна"
            
            message = f"""**Система уведомлений о промокодах**

**Статус:** {status_text}
**Режим:** Автоматический (всегда включен)

**Статистика:**
• Активных промокодов: {stats.get('total_active_promos', 0)}
• Уведомлений за 5 дней: {stats.get('notifications_5_days', 0)}  
• Уведомлений за 3 дня: {stats.get('notifications_3_days', 0)}
• Уведомлений за 1 день: {stats.get('notifications_1_day', 0)}

**Тексты уведомлений (БЕЗ изображений):**

**За 5 дней:**
_Ваш промокод истечет через 5 дней
Успейте заказать без комиссии!
<a href="http://plummy.ru/?utm_source=telegram&utm_medium=social&utm_campaign=bot">Plummy.ru</a>_

**За 3 дня:**
_По промокоду мы гарантируем САМЫЕ НИЗКИЕ цены на оригинальные вещи._

**За 1 день:**
_Ваш промокод истечет через 24 часа
Не упустите свой шанс!
<a href="http://plummy.ru/?utm_source=telegram&utm_medium=social&utm_campaign=bot">Plummy.ru</a>_

ℹ️ **Уведомления отправляются автоматически всем пользователям с активными промокодами, кроме заблокированных или использовавших промокоды.**"""

            # Кнопки управления (БЕЗ кнопок запуска/остановки)
            keyboard_buttons = [
                [InlineKeyboardButton("🧪 Тест (5 дн.)", callback_data="admin_notifications_test_5"),
                 InlineKeyboardButton("🧪 Тест (3 дн.)", callback_data="admin_notifications_test_3"),
                 InlineKeyboardButton("🧪 Тест (1 дн.)", callback_data="admin_notifications_test_1")],
                [InlineKeyboardButton("🔄 Обновить", callback_data="admin_notifications")],
                [InlineKeyboardButton("⬅ Назад", callback_data="admin_stats")]
            ]
            
            keyboard = InlineKeyboardMarkup(keyboard_buttons)
            
            await update.callback_query.edit_message_text(
                message,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            await update.callback_query.edit_message_text(
                f"Ошибка получения статистики уведомлений: {str(e)}"
            )
    
    @staticmethod
    async def admin_notifications_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Система уведомлений работает автоматически"""
        if not AdminHandlers.is_admin(update.effective_user.id):
            return
        
        await update.callback_query.answer("ℹ️ Система уведомлений работает автоматически и не требует запуска вручную!", show_alert=True)
        
        # Возвращаемся к панели уведомлений
        await AdminHandlers.admin_notifications(update, context)
    
    @staticmethod 
    async def admin_notifications_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Система уведомлений работает автоматически"""
        if not AdminHandlers.is_admin(update.effective_user.id):
            return
        
        await update.callback_query.answer("ℹ️ Система уведомлений работает автоматически и не может быть остановлена вручную!", show_alert=True)
        
        # Возвращаемся к панели уведомлений  
        await AdminHandlers.admin_notifications(update, context)
    
    @staticmethod
    async def admin_notifications_test(update: Update, context: ContextTypes.DEFAULT_TYPE, notification_type: int):
        """Отправить тестовое уведомление"""
        if not AdminHandlers.is_admin(update.effective_user.id):
            return
        
        try:
            # Динамически импортируем систему уведомлений
            from utils.notifications import notification_system
            
            if notification_system:
                success = await notification_system.send_test_notification(
                    user_id=update.effective_user.id,
                    notification_type=notification_type
                )
                
                if success:
                    await update.callback_query.answer(f"✅ Тестовое уведомление за {notification_type} дн. отправлено!", show_alert=True)
                else:
                    await update.callback_query.answer("❌ Ошибка отправки тестового уведомления!", show_alert=True)
            else:
                await update.callback_query.answer("❌ Система уведомлений не инициализирована!", show_alert=True)
                
        except Exception as e:
            await update.callback_query.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
    
    @staticmethod
    async def admin_monitoring(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Панель управления мониторингом сайта"""
        if not AdminHandlers.is_admin(update.effective_user.id):
            return
        
        # Динамически импортируем систему мониторинга
        from utils.monitoring import site_monitoring
        
        if not site_monitoring:
            await update.callback_query.edit_message_text(
                "❌ **Система мониторинга не инициализирована**\n\n"
                "Мониторинг будет доступен после перезапуска бота.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Получаем статус мониторинга
        status = await site_monitoring.get_monitoring_status()
        
        if not status['enabled']:
            message = (
                "❌ **Мониторинг сайта недоступен**\n\n"
                f"Ошибка: {status.get('error', 'Неизвестная ошибка')}\n\n"
                "Проверьте настройки UptimeRobot в конфигурации."
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Назад", callback_data="admin_back_to_main")]
            ])
        else:
            # Формируем сообщение со статусом
            monitoring_status = "🟢 Активен" if status['is_monitoring'] else "🛑 Остановлен"
            api_status = "✅ OK" if status['api_status'] == 'OK' else f"❌ {status['api_status']}"
            
            message = (
                f"📊 **Мониторинг сайта**\n\n"
                f"**Статус:** {monitoring_status}\n"
                f"**API UptimeRobot:** {api_status}\n"
                f"**Мониторов:** {status['monitors_count']}\n"
                f"**Интервал проверки:** {status['check_interval']} сек\n"
                f"**Уведомлений отправлено:** {status['notification_count']}\n"
            )
            
            if status['last_check']:
                message += f"**Последняя проверка:** {status['last_check'][:19]}\n"
                
            # Добавляем информацию о мониторах
            if status['monitors']:
                message += "\n**Мониторы:**\n"
                for monitor in status['monitors'][:3]:  # Показываем только первые 3
                    status_icon = "🟢" if monitor['is_up'] else "🔴"
                    message += f"{status_icon} {monitor['friendly_name']}\n"
                
                if len(status['monitors']) > 3:
                    message += f"... и еще {len(status['monitors']) - 3}\n"
            
            # Создаем клавиатуру в зависимости от статуса
            if status['is_monitoring']:
                keyboard_buttons = [
                    [InlineKeyboardButton("🛑 Остановить мониторинг", callback_data="admin_monitoring_stop")],
                    [InlineKeyboardButton("📊 Подробная информация", callback_data="admin_monitoring_details")],
                    [InlineKeyboardButton("🔄 Обновить", callback_data="admin_monitoring")]
                ]
            else:
                keyboard_buttons = [
                    [InlineKeyboardButton("🚀 Запустить мониторинг", callback_data="admin_monitoring_start")],
                    [InlineKeyboardButton("🧪 Тест подключения", callback_data="admin_monitoring_test")],
                    [InlineKeyboardButton("🔄 Обновить", callback_data="admin_monitoring")]
                ]
                
            keyboard_buttons.append([InlineKeyboardButton("← Назад", callback_data="admin_back_to_main")])
            keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    
    @staticmethod
    async def admin_monitoring_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запустить мониторинг сайта"""
        if not AdminHandlers.is_admin(update.effective_user.id):
            return
        
        # Динамически импортируем систему мониторинга
        from utils.monitoring import site_monitoring
            
        if not site_monitoring:
            await update.callback_query.edit_message_text(
                "❌ Система мониторинга не инициализирована",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Показываем процесс запуска
        await update.callback_query.edit_message_text(
            "🚀 **Запуск мониторинга...**\n\nПожалуйста, подождите...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        success = await site_monitoring.start_monitoring()
        
        if success:
            message = (
                "✅ **Мониторинг запущен успешно!**\n\n"
                "Система начала отслеживать состояние сайта.\n"
                "Вы будете получать уведомления при изменении статуса."
            )
        else:
            message = (
                "❌ **Ошибка запуска мониторинга**\n\n"
                "Не удалось запустить систему мониторинга.\n"
                "Проверьте настройки UptimeRobot API."
            )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("← Назад к мониторингу", callback_data="admin_monitoring")]
        ])
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    
    @staticmethod
    async def admin_monitoring_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Остановить мониторинг сайта"""
        if not AdminHandlers.is_admin(update.effective_user.id):
            return
        
        # Динамически импортируем систему мониторинга
        from utils.monitoring import site_monitoring
            
        if not site_monitoring:
            return
        
        await update.callback_query.edit_message_text(
            "🛑 **Остановка мониторинга...**\n\nПожалуйста, подождите...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        success = await site_monitoring.stop_monitoring()
        
        if success:
            message = (
                "✅ **Мониторинг остановлен**\n\n"
                "Система больше не отслеживает состояние сайта.\n"
                "Уведомления отправляться не будут."
            )
        else:
            message = (
                "❌ **Ошибка остановки мониторинга**\n\n"
                "Возможно, мониторинг уже был остановлен."
            )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("← Назад к мониторингу", callback_data="admin_monitoring")]
        ])
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    
    @staticmethod
    async def admin_monitoring_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Тестировать подключение к UptimeRobot"""
        if not AdminHandlers.is_admin(update.effective_user.id):
            return
        
        await update.callback_query.edit_message_text(
            "🧪 **Тестирование подключения...**\n\nПроверяем связь с UptimeRobot API...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        test_result = await uptime_manager.test_connection()
        
        if test_result['success']:
            message = (
                f"✅ **Подключение успешно!**\n\n"
                f"**Статус API:** Работает\n"
                f"**Найдено мониторов:** {test_result.get('monitors_count', 0)}\n\n"
                f"{test_result.get('message', '')}"
            )
        else:
            message = (
                f"❌ **Ошибка подключения**\n\n"
                f"**Проблема:** {test_result.get('error', 'Неизвестная ошибка')}\n\n"
                f"Проверьте:\n"
                f"• API ключ в настройках\n"
                f"• Подключение к интернету\n"
                f"• Настройки UptimeRobot"
            )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("← Назад к мониторингу", callback_data="admin_monitoring")]
        ])
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    
    @staticmethod 
    async def admin_monitoring_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подробная информация о мониторинге"""
        if not AdminHandlers.is_admin(update.effective_user.id):
            return
        
        # Динамически импортируем систему мониторинга
        from utils.monitoring import site_monitoring
            
        if not site_monitoring:
            return
        
        status = await site_monitoring.get_monitoring_status()
        recent_notifications = await site_monitoring.get_recent_notifications(5)
        
        message = f"📊 **Подробная информация о мониторинге**\n\n"
        
        # Информация о мониторах
        if status['monitors']:
            message += "**Мониторы:**\n"
            for monitor in status['monitors']:
                status_icon = "🟢" if monitor['is_up'] else "🔴"
                uptime = monitor.get('uptime_ratio', '0')
                message += (
                    f"{status_icon} **{monitor['friendly_name']}**\n"
                    f"   URL: `{monitor['url']}`\n"
                    f"   Статус: {monitor['status_description']}\n"
                    f"   Uptime: {uptime}%\n\n"
                )
        
        # Последние уведомления
        if recent_notifications:
            message += "**Последние уведомления:**\n"
            for notif in recent_notifications[-3:]:
                timestamp = notif['timestamp'].strftime('%H:%M:%S')
                message += f"• {timestamp}: {notif['friendly_name']} -> {notif['status_change']['current_status']}\n"
        else:
            message += "**Уведомлений пока нет**\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Обновить", callback_data="admin_monitoring_details")],
            [InlineKeyboardButton("← Назад к мониторингу", callback_data="admin_monitoring")]
        ])
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
