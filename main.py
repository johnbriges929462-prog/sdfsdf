import logging
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from database import (
    init_db, get_or_create_user, get_user_data, add_drink, 
    get_leaderboard, get_today_leaderboard, calculate_level, update_level,
    can_drink, add_vodka, remove_vodka, add_levels, get_user_by_username,
    add_group, add_user_to_group, add_group_drink, get_group_top, get_group_info
)

# Загрузить переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Админ ID (человек с правами)
ADMIN_USERNAME = 'xnxnxnxnaaa'

# Смайлики и эмодзи
VODKA_EMOJI = "🍺"
GLASS_EMOJI = "🥃"
FIRE_EMOJI = "🔥"
CROWN_EMOJI = "👑"
ROCKET_EMOJI = "🚀"
STAR_EMOJI = "⭐"

# Уровни и их описания
LEVELS = {
    1: ("Новичок", "🟢"),
    2: ("Любитель", "🟡"),
    3: ("Знаток", "🔵"),
    4: ("Профессионал", "🟣"),
    5: ("Мастер", "🔴"),
    6: ("Легенда", "🌟")
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    get_or_create_user(user.id, user.username or user.first_name)
    
    # Если команда в группе
    if update.effective_chat.type != 'private':
        group = update.effective_chat
        add_group(group.id, group.title)
        add_user_to_group(group.id, user.id)
        
        await update.message.reply_text(
            f"👋 *ВодкаМер* добавлен в группу!\n\n"
            f"Доступные команды в группе:\n"
            f"/drink - выпить рюмку\n"
            f"/profile - твой профиль\n"
            f"/grouptop - топ в группе\n"
            f"/groupstats - статистика группы",
            parse_mode='Markdown'
        )
        return
    
    keyboard = [
        [InlineKeyboardButton(f"{GLASS_EMOJI} Выпить рюмку", callback_data='drink')],
        [InlineKeyboardButton(f"{CROWN_EMOJI} Мой профиль", callback_data='profile')],
        [InlineKeyboardButton(f"{FIRE_EMOJI} Топ сегодня", callback_data='today_top')],
        [InlineKeyboardButton(f"{ROCKET_EMOJI} Общий топ", callback_data='all_top')],
        [InlineKeyboardButton(f"❓ Справка", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"""
{VODKA_EMOJI} *Добро пожаловать в ВодкаМер!* {VODKA_EMOJI}

Это игра для настоящих любителей! Считай рюмки, лезь в топ и доказывай, что ты король пьяниц!

Что я умею:
• {GLASS_EMOJI} Считать твои рюмки
• {CROWN_EMOJI} Показывать профиль с уровнем
• {FIRE_EMOJI} Выводить топ за день
• {ROCKET_EMOJI} Выводить общий топ
• 🏆 Давать достижения
• 👥 Работать в групповых чатах!

Выбери действие:
"""
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопок"""
    query = update.callback_query
    user = query.from_user
    
    # Получить или создать пользователя
    get_or_create_user(user.id, user.username or user.first_name)
    
    await query.answer()
    
    if query.data == 'drink':
        await handle_drink(query)
    elif query.data == 'profile':
        await handle_profile(query)
    elif query.data == 'today_top':
        await handle_today_top(query)
    elif query.data == 'all_top':
        await handle_all_top(query)
    elif query.data == 'help':
        await handle_help(query)
    elif query.data == 'back':
        await back_to_menu(query)

async def handle_drink(query):
    """Обработка нажатия кнопки выпить"""
    user_id = query.from_user.id
    
    # Проверить может ли пить
    can_drink_now, minutes_left = can_drink(user_id)
    
    if not can_drink_now:
        hours = minutes_left // 60
        mins = minutes_left % 60
        message_text = f"""
⏳ *Ты уже пил!*

Следующую рюмку сможешь выпить через:
⏰ {hours}ч {mins}мин

Отдыхай! 😴
"""
        await query.answer(f"Ждать ещё {hours}ч {mins}мин!", show_alert=True)
        return
    
    vodka_gain = add_drink(user_id)
    update_level(user_id)
    
    user_data = get_user_data(user_id)
    total, today, level = user_data[2], user_data[3], user_data[7]
    vodka_total = user_data[9]
    
    level_name, level_emoji = LEVELS.get(level, ("Неизвестно", "❓"))
    
    # Случайные комментарии
    comments = [
        f"Пиздец! {FIRE_EMOJI}",
        "Как блять?",
        "Нихуясе ⚡",
        "Огонь! 🔥",
        "Боже мой... 😱",
        "Сука блять! 🎯",
        "Вау! 🚀"
    ]
    
    import random
    comment = random.choice(comments)
    
    message_text = f"""
{GLASS_EMOJI} *Рюмка выпита!*

{comment}

📊 *Сегодня:* {today} рюмок {VODKA_EMOJI}
🏆 *Всего:* {total} рюмок
🌊 *Водка:* {vodka_total:.1f}л 💧
{level_emoji} *Уровень:* {level_name}

💬 Следующую можешь выпить через 5 часов!
"""
    
    keyboard = [
        [InlineKeyboardButton(f"{CROWN_EMOJI} Мой профиль", callback_data='profile')],
        [InlineKeyboardButton(f"{FIRE_EMOJI} Топ сегодня", callback_data='today_top')],
        [InlineKeyboardButton(f"↩️ Назад", callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_profile(query):
    """Обработка профиля"""
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    
    if not user_data:
        await query.edit_message_text("Ошибка! Пользователь не найден.")
        return
    
    username, total, today, level = user_data[1], user_data[2], user_data[3], user_data[7]
    vodka_total = user_data[9]
    level_name, level_emoji = LEVELS.get(level, ("Неизвестно", "❓"))
    
    # Прогресс до следующего уровня
    level_thresholds = [0, 10, 50, 100, 200, 500, 1000]
    current_threshold = level_thresholds[level - 1] if level <= len(level_thresholds) else 0
    next_threshold = level_thresholds[level] if level < len(level_thresholds) else 1000
    progress = total - current_threshold
    needed = next_threshold - current_threshold
    
    progress_bar = "▓" * min(10, int((progress / needed) * 10)) + "░" * (10 - min(10, int((progress / needed) * 10)))
    
    message_text = f"""
👤 *Твой профиль*

👤 *Имя:* {username or 'Аноним'}
{level_emoji} *Уровень:* {level_name} ({level}/6)

📊 *Статистика:*
  🍺 Всего выпито: {total} рюмок
  🔥 Сегодня: {today} рюмок
  💧 Водка: {vodka_total:.1f} литров
  
📈 *Прогресс до следующего уровня:*
`{progress_bar}`
{progress}/{needed} рюмок

🎯 *Цель:* Достичь уровня Легенда и выпить 1000 рюмок!
"""
    
    keyboard = [
        [InlineKeyboardButton(f"{GLASS_EMOJI} Выпить", callback_data='drink')],
        [InlineKeyboardButton(f"↩️ Назад", callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_today_top(query):
    """Топ за сегодня"""
    leaderboard = get_today_leaderboard(10)
    
    message_text = f"{FIRE_EMOJI} *Топ игроков за СЕГОДНЯ* {FIRE_EMOJI}\n\n"
    
    medals = ["🥇", "🥈", "🥉"]
    
    for i, (user_id, username, drinks) in enumerate(leaderboard, 1):
        medal = medals[i-1] if i <= 3 else f"{i}️⃣"
        name = username or f"Пользователь {user_id}"
        message_text += f"{medal} *{name}* — {drinks} {VODKA_EMOJI}\n"
    
    if not leaderboard:
        message_text += "Пока никто не пил сегодня. Будь первым!"
    
    message_text += f"\n_Обновляется в реальном времени!_"
    
    keyboard = [
        [InlineKeyboardButton(f"{GLASS_EMOJI} Выпить", callback_data='drink')],
        [InlineKeyboardButton(f"↩️ Назад", callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_all_top(query):
    """Общий топ"""
    leaderboard = get_leaderboard(10)
    
    message_text = f"{CROWN_EMOJI} *ОБЩИЙ ТОП ВСЕХ ВРЕМЁН* {CROWN_EMOJI}\n\n"
    
    medals = ["🥇", "🥈", "🥉"]
    
    for i, (user_id, username, total, level) in enumerate(leaderboard, 1):
        medal = medals[i-1] if i <= 3 else f"{i}️⃣"
        name = username or f"Пользователь {user_id}"
        level_name, level_emoji = LEVELS.get(level, ("?", "❓"))
        message_text += f"{medal} *{name}* — {total} {VODKA_EMOJI} {level_emoji}\n"
    
    if not leaderboard:
        message_text += "Топ ещё пуст!"
    
    message_text += f"\n_Ты можешь быть в этом списке!_"
    
    keyboard = [
        [InlineKeyboardButton(f"{GLASS_EMOJI} Выпить", callback_data='drink')],
        [InlineKeyboardButton(f"↩️ Назад", callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_help(query):
    """Справка"""
    message_text = f"""
❓ *КАК ИГРАТЬ?*

{VODKA_EMOJI} *ВодкаМер* - это игра, где ты соревнуешься с друзьями кто больше выпьет!

*Как это работает:*
1️⃣ Нажимай кнопку "{GLASS_EMOJI} Выпить рюмку"
2️⃣ Каждая рюмка считается и добавляется в счет
3️⃣ Лезь в топ и доказывай свои способности!
4️⃣ Поднимай уровень с каждой выпитой рюмкой

*Уровни:*
🟢 1 - Новичок (0-9 рюмок)
🟡 2 - Любитель (10-49)
🔵 3 - Знаток (50-99)
🟣 4 - Профессионал (100-199)
🔴 5 - Мастер (200-499)
🌟 6 - Легенда (500+)

*Счетчик обнуляется ежедневно!* 🔄

⚠️ *ИГРОВАЯ СПРАВКА:*
Помни, это только игра! Будь осторожен с алкоголем в реальной жизни!

Сыграй и лезь в топ! {ROCKET_EMOJI}
"""
    
    keyboard = [
        [InlineKeyboardButton(f"↩️ Назад", callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')

async def back_to_menu(query):
    """Вернуться в главное меню"""
    keyboard = [
        [InlineKeyboardButton(f"{GLASS_EMOJI} Выпить рюмку", callback_data='drink')],
        [InlineKeyboardButton(f"{CROWN_EMOJI} Мой профиль", callback_data='profile')],
        [InlineKeyboardButton(f"{FIRE_EMOJI} Топ сегодня", callback_data='today_top')],
        [InlineKeyboardButton(f"{ROCKET_EMOJI} Общий топ", callback_data='all_top')],
        [InlineKeyboardButton(f"❓ Справка", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = f"""
{VODKA_EMOJI} *ВодкаМер* {VODKA_EMOJI}

Выбери действие:
"""
    
    await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')

# ===== ГРУППОВЫЕ КОМАНДЫ =====

async def group_drink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /drink в группе"""
    user = update.effective_user
    group = update.effective_chat
    
    get_or_create_user(user.id, user.username or user.first_name)
    add_group(group.id, group.title)
    add_user_to_group(group.id, user.id)
    
    # Проверить может ли пить
    can_drink_now, minutes_left = can_drink(user.id)
    
    if not can_drink_now:
        hours = minutes_left // 60
        mins = minutes_left % 60
        await update.message.reply_text(
            f"⏳ {user.mention_markdown_v2()} уже пил!\n\n"
            f"Следующую рюмку через: ⏰ {hours}ч {mins}мин",
            parse_mode='MarkdownV2'
        )
        return
    
    vodka_gain = add_drink(user.id)
    add_group_drink(group.id, user.id)
    update_level(user.id)
    
    user_data = get_user_data(user.id)
    total, level = user_data[2], user_data[7]
    vodka_total = user_data[9]
    
    level_name, level_emoji = LEVELS.get(level, ("?", "❓"))
    
    message_text = f"""
{GLASS_EMOJI} *{user.first_name} выпил рюмку!*

🥃 +1 рюмка
💧 +{vodka_gain}л водки

📊 *Всего:* {total} рюмок
🌊 *Водка:* {vodka_total:.1f}л
{level_emoji} *Уровень:* {level_name}
"""
    
    await update.message.reply_text(message_text, parse_mode='Markdown')

async def group_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /profile в группе"""
    user = update.effective_user
    
    get_or_create_user(user.id, user.username or user.first_name)
    user_data = get_user_data(user.id)
    
    if not user_data:
        await update.message.reply_text("Ошибка! Пользователь не найден.")
        return
    
    total, level = user_data[2], user_data[7]
    vodka_total = user_data[9]
    level_name, level_emoji = LEVELS.get(level, ("?", "❓"))
    
    message_text = f"""
👤 *Профиль {user.first_name}*

{level_emoji} *Уровень:* {level_name} ({level}/6)
🍺 *Выпито:* {total} рюмок
💧 *Водка:* {vodka_total:.1f}л
"""
    
    await update.message.reply_text(message_text, parse_mode='Markdown')

async def group_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /grouptop - топ в группе"""
    group = update.effective_chat
    
    add_group(group.id, group.title)
    
    leaderboard = get_group_top(group.id, 10)
    
    message_text = f"{FIRE_EMOJI} *Топ в группе {group.title}* {FIRE_EMOJI}\n\n"
    
    medals = ["🥇", "🥈", "🥉"]
    
    if not leaderboard:
        message_text += "Пока никто не выпивал в группе!"
    else:
        for i, (username, drinks, level) in enumerate(leaderboard, 1):
            medal = medals[i-1] if i <= 3 else f"{i}️⃣"
            level_name, level_emoji = LEVELS.get(level, ("?", "❓"))
            name = username or f"Пользователь"
            message_text += f"{medal} *{name}* — {drinks} рюмок {level_emoji}\n"
    
    await update.message.reply_text(message_text, parse_mode='Markdown')

async def group_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /groupstats - статистика группы"""
    group = update.effective_chat
    
    add_group(group.id, group.title)
    group_info = get_group_info(group.id)
    
    if not group_info:
        group_name, total_drinks = group.title, 0
    else:
        group_name, total_drinks = group_info
    
    message_text = f"""
📊 *Статистика группы*

👥 *Группа:* {group_name}
🍺 *Всего выпито:* {total_drinks} рюмок
🔥 *Статус:* Активна!

Напоминание: рюмку можно выпить раз в 5 часов! ⏳
"""
    
    await update.message.reply_text(message_text, parse_mode='Markdown')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ошибок"""
    logger.error(f"Ошибка: {context.error}")

# ===== АДМИН КОМАНДЫ =====

def is_admin(username):
    """Проверить является ли пользователь админом"""
    clean_username = username.lstrip('@') if username else ""
    return clean_username.lower() == ADMIN_USERNAME.lower()

async def admin_vodka(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /vodka - админ добавляет водку: /vodka 50 (ник)"""
    if not is_admin(update.effective_user.username):
        await update.message.reply_text("❌ У тебя нет прав! Эта команда только для админа.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ Использование: /vodka (количество) (ник)\nПример: /vodka 50 @username")
        return
    
    try:
        amount = int(context.args[0])
        target_username = context.args[1]
        
        target_user_id = get_user_by_username(target_username)
        if not target_user_id:
            await update.message.reply_text(f"❌ Пользователь {target_username} не найден!")
            return
        
        add_vodka(target_user_id, amount)
        
        user_data = get_user_data(target_user_id)
        vodka_total = user_data[9]
        
        await update.message.reply_text(
            f"✅ Админ добавил {amount}л водки пользователю {target_username}!\n"
            f"Всего водки: {vodka_total:.1f}л 💧"
        )
    except ValueError:
        await update.message.reply_text("❌ Количество должно быть числом!")

async def admin_donat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /donat - админ отправляет донат: /donat (текст)"""
    if not is_admin(update.effective_user.username):
        await update.message.reply_text("❌ У тебя нет прав! Эта команда только для админа.")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Использование: /donat (текст)\nПример: /donat 💎 Премиум пакет")
        return
    
    donat_text = " ".join(context.args)
    await update.message.reply_text(
        f"🎁 *НОВЫЙ ДОНАТ!* 🎁\n\n{donat_text}\n\n_Спасибо за поддержку!_",
        parse_mode='Markdown'
    )

async def admin_lvlup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /lvlup - админ повышает уровень: /lvlup 10 (ник)"""
    if not is_admin(update.effective_user.username):
        await update.message.reply_text("❌ У тебя нет прав! Эта команда только для админа.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ Использование: /lvlup (количество) (ник)\nПример: /lvlup 5 @username")
        return
    
    try:
        levels = int(context.args[0])
        target_username = context.args[1]
        
        target_user_id = get_user_by_username(target_username)
        if not target_user_id:
            await update.message.reply_text(f"❌ Пользователь {target_username} не найден!")
            return
        
        add_levels(target_user_id, levels)
        
        user_data = get_user_data(target_user_id)
        new_level = user_data[7]
        level_name, level_emoji = LEVELS.get(new_level, ("Неизвестно", "❓"))
        
        await update.message.reply_text(
            f"✅ Админ повысил уровень на {levels}ур игроку {target_username}!\n"
            f"Новый уровень: {level_emoji} {level_name} ({new_level}/6)"
        )
    except ValueError:
        await update.message.reply_text("❌ Количество уровней должно быть числом!")

async def admin_remove_vodka(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /removevodka - админ отнимает водку: /removevodka 5 (ник)"""
    if not is_admin(update.effective_user.username):
        await update.message.reply_text("❌ У тебя нет прав! Эта команда только для админа.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ Использование: /removevodka (количество) (ник)\nПример: /removevodka 5 @username\n⚠️ Макс 10л за раз")
        return
    
    try:
        amount = int(context.args[0])
        target_username = context.args[1]
        
        target_user_id = get_user_by_username(target_username)
        if not target_user_id:
            await update.message.reply_text(f"❌ Пользователь {target_username} не найден!")
            return
        
        if amount > 10:
            await update.message.reply_text("❌ Можно отнять максимум 10л водки за раз!")
            return
        
        remove_vodka(target_user_id, amount)
        
        user_data = get_user_data(target_user_id)
        vodka_total = user_data[9]
        
        await update.message.reply_text(
            f"✅ Админ отнял {amount}л водки у пользователя {target_username}!\n"
            f"Осталось водки: {vodka_total:.1f}л 💧"
        )
    except ValueError:
        await update.message.reply_text("❌ Количество должно быть числом!")

def main():
    """Главная функция"""
    # Инициализация БД
    init_db()
    
    # Получить токен бота
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN не найден в .env файле!")
    
    # Создать приложение
    app = Application.builder().token(token).build()
    
    # Регистрация обработчиков
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('vodka', admin_vodka))
    app.add_handler(CommandHandler('donat', admin_donat))
    app.add_handler(CommandHandler('lvlup', admin_lvlup))
    app.add_handler(CommandHandler('removevodka', admin_remove_vodka))
    
    # Групповые команды
    app.add_handler(CommandHandler('drink', group_drink))
    app.add_handler(CommandHandler('profile', group_profile))
    app.add_handler(CommandHandler('grouptop', group_top))
    app.add_handler(CommandHandler('groupstats', group_stats))
    
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)
    
    # Запуск бота
    logger.info("🤖 Бот запущен!")
    print(f"{VODKA_EMOJI} ВодкаМер запущен! {VODKA_EMOJI}")
    
    app.run_polling()

if __name__ == '__main__':
    main()
