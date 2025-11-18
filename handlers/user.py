"""
Обработчики для пользователей бота PlummyPromo
"""

from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from datetime import datetime, timedelta

from database.database import db
from data.faq import get_faq_categories, get_category_questions, search_faq
from utils.config import Config
from utils.analytics import AnalyticsHelper
from utils.promo import PromoCodeGenerator
from utils.woocommerce import woo_manager
from utils.media import media_manager


class UserHandlers:
    """Обработчики для пользователей"""
    
    @staticmethod
    def get_main_keyboard():
        """Получить основную клавиатуру"""
        keyboard = [
            ["Получить промокод"],
            ["FAQ", "Поддержка"]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    @staticmethod
    async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        
        # Парсим UTM параметры из аргументов команды
        utm_data = {}
        if context.args:
            start_param = '_'.join(context.args)
            utm_data = AnalyticsHelper.parse_utm_params(start_param)
        
        referral_source = AnalyticsHelper.detect_referral_source(utm_data)
        
        # Регистрируем или обновляем пользователя
        await db.user.get_or_create_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            referral_source=referral_source
        )
        
        # Отслеживаем действие
        await db.analytics.track_user_action(
            user_id=user.id,
            action_type='start',
            referral_source=referral_source,
            utm_data=utm_data
        )
        
        # Приветственное сообщение с изображением
        welcome_text = """Добро пожаловать в Plummy!

Мы делаем заказ одежды из зарубежных магазинов простым и выгодным. Тысячи товаров в каталоге и быстрый выкуп любой вещи под заказ.

Нажми на «Получить промокод»."""
        
        # Отправляем приветственное изображение с текстом
        await media_manager.send_photo_with_text(
            update=update,
            event='hello',
            text=welcome_text,
            parse_mode=ParseMode.HTML,
            reply_markup=UserHandlers.get_main_keyboard()
        )
    
    @staticmethod
    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = f"""
🤖 **Помощь по боту {Config.SHOP_NAME}**

**🎁 Основная функция:** Получение персональных промокодов со скидкой {Config.PROMO_DISCOUNT_PERCENT}%

📋 **Команды:**
• /start - Начать работу с ботом
• /promo - Получить промокод  
• /faq - Часто задаваемые вопросы
• /help - Показать эту справку

🔘 **Кнопки:**
• **Получить промокод** - Получить уникальную скидку
• **FAQ** - Ответы на вопросы о магазине
• **Поддержка** - Связь с нашей службой поддержки

💡 **Как пользоваться:**
1. Нажми "Получить промокод"
2. Скопируй код и используй при покупке на {Config.SHOP_URL}  
3. При вопросах жми "FAQ" или "Поддержка"

🛍 **Сайт магазина:** {Config.SHOP_URL}
        """
        
        await update.message.reply_text(
            help_text,
            parse_mode=ParseMode.HTML
        )
    
    @staticmethod
    async def promo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /promo и кнопки получения промокода"""
        try:
            user = update.effective_user
            
            # Проверяем ВСЕ промокоды пользователя (включая использованные)
            existing_codes = await db.promo.get_user_promo_codes(user.id)
            
            if existing_codes:
                # У пользователя уже есть промокоды, проверяем использовал ли он хотя бы один
                used_codes = [code for code in existing_codes if code['is_used']]
                active_codes = [code for code in existing_codes if not code['is_used']]
                
                # Опционально синхронизируем активные промокоды с WooCommerce (если включено)
                try:
                    if Config.WOOCOMMERCE_ENABLED and woo_manager.is_enabled():
                        codes_to_remove = []  # Промокоды для удаления из активных
                        
                        for active_code in active_codes:
                            sync_result = await woo_manager.sync_coupon_status(
                                active_code['code'], 
                                active_code.get('woocommerce_id')
                            )
                            
                            if sync_result.get("synced", False):
                                # Промокод найден на сайте
                                if sync_result.get("is_used", False):
                                    # Промокод использован в WooCommerce, обновляем локальную базу
                                    await db.promo.use_promo_code(active_code['code'])
                                    used_codes.append(active_code)
                                    codes_to_remove.append(active_code)
                            else:
                                # Промокод НЕ найден на сайте (удален администратором)
                                error_msg = sync_result.get("error", "").lower()
                                if "не найден" in error_msg or "not found" in error_msg:
                                    # Отмечаем промокод как использованный, чтобы скрыть от пользователя
                                    await db.promo.use_promo_code(active_code['code'])
                                    used_codes.append(active_code)
                                    codes_to_remove.append(active_code)
                                    
                                    import logging
                                    logging.getLogger(__name__).info(f"Промокод {active_code['code']} удален с сайта администратором, отмечен как использованный в боте")
                        
                        # Удаляем синхронизированные промокоды из списка активных
                        for code_to_remove in codes_to_remove:
                            if code_to_remove in active_codes:
                                active_codes.remove(code_to_remove)
                except Exception as e:
                    # Если WooCommerce недоступен, продолжаем без синхронизации
                    import logging
                    logging.getLogger(__name__).warning(f"WooCommerce синхронизация недоступна: {e}")
                
                # Если пользователь использовал хотя бы один промокод - показываем сообщение "уже использовал"
                if used_codes:
                    message_text = """Ты уже успешно использовал свой промокод, спасибо!

Но даже без акций мы стараемся держать цены ниже чем у конкурентов, убедись в этом сам
<a href="http://plummy.ru/?utm_source=telegram&utm_medium=social&utm_campaign=bot">Plummy.ru</a>"""
                else:
                    # Пользователь не использовал ни одного промокода, проверяем активные промокоды на истечение
                    valid_active_codes = []
                    
                    for active_code in active_codes:
                        # Сначала пытаемся получить РЕАЛЬНУЮ дату истечения с сайта (если WooCommerce включен)
                        expiry_date = None
                        
                        if Config.WOOCOMMERCE_ENABLED and woo_manager.is_enabled():
                            try:
                                real_expiry_date = await woo_manager.get_coupon_expiry_date(active_code['code'])
                                if real_expiry_date:
                                    # Используем реальную дату с сайта
                                    expiry_date = real_expiry_date
                            except Exception as e:
                                # При ошибке WooCommerce используем локальный расчет (ниже)
                                import logging
                                logging.getLogger(__name__).warning(f"Ошибка получения даты истечения с WooCommerce для {active_code['code']}: {e}")
                        
                        # Fallback: рассчитываем дату по настройкам бота (если не получили с сайта)
                        if not expiry_date:
                            created_date = datetime.strptime(active_code['created_date'][:19], "%Y-%m-%d %H:%M:%S")
                            duration_days = await db.settings.get_promo_duration_days()
                            expiry_date = created_date + timedelta(days=duration_days)
                        
                        # Проверяем, не истек ли промокод
                        if datetime.now() <= expiry_date:
                            valid_active_codes.append((active_code, expiry_date))
                    
                    if valid_active_codes:
                        # Есть действующие промокоды, показываем первый
                        active_code, expiry_date = valid_active_codes[0]
                        expiry_formatted = expiry_date.strftime("%d.%m.%Y в %H:%M")
                        discount_percent = active_code.get('discount_percent', 5)
                        
                        message_text = f"""У вас уже есть активный промокод на {discount_percent}%!

Код: <code>{active_code['code']}</code>

Истекает: {expiry_formatted}

Как использовать:
1️⃣ Перейдите на сайт <a href="http://plummy.ru/?utm_source=telegram&utm_medium=social&utm_campaign=bot">plummy.ru</a>
2️⃣ Выберите товары и добавьте в корзину / воспользуйтесь формой для выкупа
3️⃣ При оформлении заказа введите промокод

Его можно использовать только один раз."""
                    else:
                        # Все промокоды истекли
                        message_text = """Срок действия промокода истек(

Но даже без акций мы стараемся держать цены ниже чем у конкурентов, убедись в этом сам
<a href="http://plummy.ru/?utm_source=telegram&utm_medium=social&utm_campaign=bot">Plummy.ru</a>"""
            else:
                # У пользователя нет промокодов, создаем первый
                try:
                    promo_code = await db.promo.create_promo_code(
                        user_id=user.id,
                        username=user.username
                        # discount_percent будет взят из настроек базы данных
                    )
                    
                    # Отслеживаем получение промокода
                    await db.analytics.track_user_action(
                        user_id=user.id,
                        action_type='promo_request'
                    )
                    
                    # Рассчитываем дату истечения из настроек
                    duration_days = await db.settings.get_promo_duration_days()
                    expiry_date = datetime.now() + timedelta(days=duration_days)
                    expiry_formatted = expiry_date.strftime("%d.%m.%Y в %H:%M")
                    
                    message_text = f"""🎉 Ваш персональный промокод готов!

Код: <code>{promo_code}</code>

При его применении, мы полностью уберем нашу комиссию и вы заплатите только за расходы на выкуп + логистику.

Истекает: {expiry_formatted}

Как использовать:
1️⃣ Перейдите на сайт <a href="http://plummy.ru/?utm_source=telegram&utm_medium=social&utm_campaign=bot">plummy.ru</a>
2️⃣ Выберите товары и добавьте в корзину / воспользуйтесь формой для выкупа
3️⃣ При оформлении заказа введите промокод

Его можно использовать только один раз."""
                except Exception as e:
                    message_text = """😔 Произошла ошибка при создании промокода.
Попробуйте позже или обратитесь в поддержку."""
            
            # Создаем кнопки в зависимости от ситуации пользователя
            buttons = []
            
            # Для сообщений об истечении срока или об уже использованном промокоде кнопки не нужны
            if "Срок действия промокода истек" in message_text or "уже успешно использовал" in message_text:
                # Никаких кнопок для истекших или использованных промокодов
                pass
            else:
                # Показываем только кнопку перехода на сайт
                buttons.append([InlineKeyboardButton("Перейти на сайт", url="http://plummy.ru/?utm_source=telegram&utm_medium=social&utm_campaign=bot")])
            
            # Создаем клавиатуру только если есть кнопки
            keyboard = InlineKeyboardMarkup(buttons) if buttons else None
            
            # Определяем какое изображение отправить в зависимости от типа сообщения
            if "уже успешно использовал" in message_text:
                # Пользователь уже использовал промокод - изображение done
                event = 'done'
            elif "Срок действия промокода истек" in message_text:
                # Промокод истек - изображение finish
                event = 'finish'  
            elif ("персональный промокод готов" in message_text or 
                  "У вас уже есть активный промокод" in message_text):
                # Новый промокод или показ существующего - изображение promo
                event = 'promo'
            else:
                # Для остальных случаев (например, ошибки) отправляем без изображения
                await update.message.reply_text(
                    message_text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                )
                return
            
            # Отправляем сообщение с соответствующим изображением
            await media_manager.send_photo_with_text(
                update=update,
                event=event,
                text=message_text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
        except Exception as e:
            # Логируем ошибку для отладки
            import logging
            logging.getLogger(__name__).error(f"Ошибка в promo_command: {e}", exc_info=True)
            
            # Отправляем пользователю информативное сообщение
            error_message = """😔 Произошла ошибка при обработке вашего запроса.
Попробуйте позже или обратитесь в поддержку."""
            
            try:
                await update.message.reply_text(error_message, parse_mode=ParseMode.HTML)
            except Exception:
                # Если даже отправка сообщения об ошибке не удалась, ничего не делаем
                pass
    
    @staticmethod
    async def faq_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик FAQ"""
        # Отслеживаем просмотр FAQ
        await db.analytics.track_user_action(
            user_id=update.effective_user.id,
            action_type='faq_view'
        )
        
        faq_text = """<b><a href="https://yandex.ru/profile/35414701593">Отзывы</a></b>

<b>В каталоге нет того, что я хочу заказать</b>

У нас можно заказать не только из каталога, но и просто заполнив форму на выкуп <a href="http://plummy.ru/buyout?utm_source=telegram&utm_medium=social&utm_campaign=bot">plummy.ru/buyout</a>

<b>Как выбрать размер?</b>

В нашем каталоге мы показываем размеры обуви в EU, одежду – в стандартной размерной сетке бренда. Если у вас появились трудности с выбором размера – напишите менеджеру, он поможет.

<b>Может ли прийти не оригинальная вещь?</b>

Такого не может произойти, так как мы выкупаем только из оригинальных бутиков, все товары имеют cеpтификаты пoдлинности и бирки.

<b>Оформил заказ на сайте, что делать дальше?</b>

С вами оперативно свяжется наш менеджер, чтобы подтвердить заказ.

<b>Можно вернуть, если не подошел размер / стиль?</b>

Мы выкупаем товар из-за границы, и пока он доставляется, срок возврата в бутиках обычно заканчивается. Поэтому оформить моментальный возврат мы не можем. Однако мы можем принять вещь на реализацию — разместим её на наших и партнёрских площадках, продадим и вернём вам всю сумму после продажи."""
        
        await update.message.reply_text(faq_text, parse_mode=ParseMode.HTML)
    
    
    @staticmethod
    async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки Поддержка"""
        support_text = "Вы всегда можете написать нашей службе поддержки в Telegram: @hey_plummy — рассчитать стоимость выкупа, уточнить по срокам и размерам, узнать статус заказа."
        
        # Отправляем изображение поддержки с текстом
        await media_manager.send_photo_with_text(
            update=update,
            event='help',
            text=support_text
        )
    
    @staticmethod
    async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик inline кнопок"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data.startswith("faq_"):
            await UserHandlers.show_faq_category(update, context, data[4:])
        elif data == "get_promo":
            # Имитируем получение промокода через кнопку
            await UserHandlers.promo_command(update, context)
    
    @staticmethod
    async def show_faq_category(update: Update, context: ContextTypes.DEFAULT_TYPE, category_key: str):
        """Показать вопросы категории FAQ"""
        category_data = get_category_questions(category_key)
        
        if not category_data:
            await update.callback_query.edit_message_text("❌ Категория не найдена")
            return
        
        text = f"**{category_data['title']}**\n\n"
        
        for i, question_data in enumerate(category_data['questions'], 1):
            text += f"**{i}. {question_data['question']}**\n"
            text += f"{question_data['answer']}\n\n"
        
        # Кнопка назад
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("← Назад к категориям", callback_data="back_to_faq")]
        ])
        
        await update.callback_query.edit_message_text(
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
    
    
    @staticmethod
    async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений и кнопок"""
        text = update.message.text
        user = update.effective_user
        
        if text == "Получить промокод":
            await UserHandlers.promo_command(update, context)
        elif text == "FAQ":
            await UserHandlers.faq_command(update, context)
        elif text == "Поддержка":
            await UserHandlers.support_command(update, context)
        else:
            # Проверяем, есть ли у пользователя промокод с запрошенной обратной связью
            try:
                async with db.manager.get_connection() as conn:
                    cursor = await conn.execute("""
                        SELECT code FROM promocodes 
                        WHERE user_id = ? 
                        AND feedback_requested = 1 
                        AND is_used = 0
                        AND code NOT IN (SELECT promo_code FROM feedback WHERE user_id = ?)
                        ORDER BY feedback_request_date DESC
                        LIMIT 1
                    """, (user.id, user.id))
                    result = await cursor.fetchone()
                    
                    if result:
                        # У пользователя есть промокод с запрошенной обратной связью
                        promo_code = result[0]
                        # Обрабатываем обратную связь
                        await UserHandlers.handle_feedback(update, context, text, promo_code)
                    else:
                        # Не отвечаем на произвольные сообщения
                        # Пользователь должен использовать кнопки
                        pass
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Ошибка проверки обратной связи: {e}")
                pass
    
    @staticmethod
    async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE, feedback_text: str, promo_code: str = 'UNKNOWN'):
        """Обработать обратную связь от пользователя"""
        user = update.effective_user
        
        try:
            # Сохраняем обратную связь в базу данных
            async with db.manager.get_connection() as conn:
                await conn.execute("""
                    INSERT INTO feedback (user_id, promo_code, feedback_text)
                    VALUES (?, ?, ?)
                """, (user.id, promo_code, feedback_text))
                await conn.commit()
            
            # Формируем сообщение для администраторов
            user_contact = f"@{user.username}" if user.username else f"ID: {user.id}"
            user_name = user.first_name or "Пользователь"
            if user.last_name:
                user_name += f" {user.last_name}"
            
            admin_message = f"""📝 Получена обратная связь от пользователя, не активировавшего промокод

👤 Пользователь: {user_name}
📞 Контакт: {user_contact}
🎫 Промокод: {promo_code}

💬 Обратная связь:
{feedback_text}"""
            
            # Отправляем всем администраторам
            for admin_id in Config.ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=admin_message,
                        parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"Не удалось отправить обратную связь администратору {admin_id}: {e}")
            
            # Благодарим пользователя
            await update.message.reply_text(
                "Спасибо за вашу обратную связь! Мы обязательно учтем ваши замечания и постараемся стать лучше.",
                parse_mode=ParseMode.HTML
            )
            
            import logging
            logging.getLogger(__name__).info(f"📝 Получена обратная связь от пользователя {user.id}")
            
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"❌ Ошибка обработки обратной связи: {e}")
            await update.message.reply_text(
                "Произошла ошибка при отправке обратной связи. Попробуйте позже.",
                parse_mode=ParseMode.HTML
            )
