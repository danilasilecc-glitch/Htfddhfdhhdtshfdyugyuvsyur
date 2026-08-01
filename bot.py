import os
import time
import sqlite3
import random
import threading
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# === КОНФИГ ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не задан в переменных окружения!")

bot = telebot.TeleBot(BOT_TOKEN)

# === БАЗА ДАННЫХ ===
conn = sqlite3.connect("rpg_data.db", check_same_thread=False)
cursor = conn.cursor()

# Создаём таблицы
cursor.execute('''
CREATE TABLE IF NOT EXISTS players (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    display_name TEXT,
    level INTEGER DEFAULT 1,
    exp INTEGER DEFAULT 0,
    exp_to_next INTEGER DEFAULT 100,
    coins INTEGER DEFAULT 50,
    hp INTEGER DEFAULT 100,
    max_hp INTEGER DEFAULT 100,
    attack INTEGER DEFAULT 10,
    defense INTEGER DEFAULT 5,
    clan_id INTEGER DEFAULT NULL,
    head_armor TEXT DEFAULT NULL,
    chest_armor TEXT DEFAULT NULL,
    legs_armor TEXT DEFAULT NULL,
    boots_armor TEXT DEFAULT NULL,
    weapon TEXT DEFAULT NULL
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS clans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    leader_id INTEGER,
    members TEXT DEFAULT '',
    created_at INTEGER
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS shop (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    type TEXT,
    stat TEXT,
    value INTEGER,
    price INTEGER
)
''')

# Добавляем товары в магазин (если пусто)
cursor.execute("SELECT COUNT(*) FROM shop")
if cursor.fetchone()[0] == 0:
    items = [
        ("Шлем новичка", "head", "defense", 2, 50),
        ("Кираса воина", "chest", "defense", 3, 100),
        ("Поножи разведчика", "legs", "defense", 2, 75),
        ("Сапоги скорости", "boots", "defense", 1, 50),
        ("Меч стали", "weapon", "attack", 3, 120),
        ("Топор варвара", "weapon", "attack", 5, 200),
        ("Железный шлем", "head", "defense", 4, 150),
        ("Кираса героя", "chest", "defense", 6, 250),
        ("Поножи титана", "legs", "defense", 4, 180),
        ("Сапоги ветра", "boots", "defense", 3, 120),
        ("Меч дракона", "weapon", "attack", 8, 350)
    ]
    for item in items:
        cursor.execute("INSERT INTO shop (name, type, stat, value, price) VALUES (?, ?, ?, ?, ?)", item)
    conn.commit()

conn.commit()

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

def get_player(user_id):
    cursor.execute("SELECT * FROM players WHERE user_id = ?", (user_id,))
    return cursor.fetchone()

def create_player(user_id, username):
    cursor.execute(
        "INSERT INTO players (user_id, username, display_name) VALUES (?, ?, ?)",
        (user_id, username, username)
    )
    conn.commit()

def update_exp(user_id, exp_gain):
    cursor.execute("SELECT exp, exp_to_next, level FROM players WHERE user_id = ?", (user_id,))
    exp, exp_to_next, level = cursor.fetchone()
    new_exp = exp + exp_gain
    leveled_up = False
    while new_exp >= exp_to_next:
        new_exp -= exp_to_next
        level += 1
        exp_to_next = int(exp_to_next * 1.5)
        leveled_up = True
        cursor.execute(
            "UPDATE players SET max_hp = max_hp + 10, attack = attack + 2, defense = defense + 1 WHERE user_id = ?",
            (user_id,)
        )
    cursor.execute(
        "UPDATE players SET exp = ?, exp_to_next = ?, level = ? WHERE user_id = ?",
        (new_exp, exp_to_next, level, user_id)
    )
    conn.commit()
    return leveled_up, level

def get_total_armor(user_id):
    cursor.execute("SELECT head_armor, chest_armor, legs_armor, boots_armor FROM players WHERE user_id = ?", (user_id,))
    armor = cursor.fetchone()
    total = 0
    for slot in armor:
        if slot:
            cursor.execute("SELECT value FROM shop WHERE name = ?", (slot,))
            res = cursor.fetchone()
            if res:
                total += res[0]
    return total

def get_weapon_attack(user_id):
    cursor.execute("SELECT weapon FROM players WHERE user_id = ?", (user_id,))
    weapon = cursor.fetchone()[0]
    if weapon:
        cursor.execute("SELECT value FROM shop WHERE name = ?", (weapon,))
        res = cursor.fetchone()
        if res:
            return res[0]
    return 0

def get_player_stats(user_id):
    p = get_player(user_id)
    if not p:
        return None
    return {
        "display_name": p[2],
        "level": p[3],
        "exp": p[4],
        "exp_to_next": p[5],
        "coins": p[6],
        "hp": p[7],
        "max_hp": p[8],
        "attack": p[9] + get_weapon_attack(user_id),
        "defense": p[10] + get_total_armor(user_id),
        "head_armor": p[12],
        "chest_armor": p[13],
        "legs_armor": p[14],
        "boots_armor": p[15],
        "weapon": p[16]
    }

# === КЛАВИАТУРЫ ===

def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⚔️ Дуэль", callback_data="duel"),
        InlineKeyboardButton("👤 Профиль", callback_data="profile"),
        InlineKeyboardButton("🏪 Магазин", callback_data="shop"),
        InlineKeyboardButton("🏆 Топ", callback_data="top"),
        InlineKeyboardButton("📜 Кланы", callback_data="clans"),
        InlineKeyboardButton("📊 Помощь", callback_data="help")
    )
    return kb

def duel_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🔍 Найти противника", callback_data="find_opponent"),
        InlineKeyboardButton("📋 Отмена", callback_data="cancel_duel"),
        InlineKeyboardButton("🔙 Назад", callback_data="back_main")
    )
    return kb

# === ЗАЩИТА И АТАКА ===

PROTECT_COMBOS = {
    "head_chest": {"head": True, "chest": True, "belt": False, "hands": False, "legs": False},
    "chest_belt": {"head": False, "chest": True, "belt": True, "hands": False, "legs": False},
    "chest_hands": {"head": False, "chest": True, "belt": False, "hands": True, "legs": False},
    "belt_legs": {"head": False, "chest": False, "belt": True, "hands": False, "legs": True}
}

ATTACK_COMBOS = {
    "head_chest": ["head", "chest"],
    "chest_belt": ["chest", "belt"],
    "chest_hands": ["chest", "hands"],
    "belt_legs": ["belt", "legs"]
}

COMBAT_STATE = {}

def start_battle(player1, player2):
    COMBAT_STATE[player1] = {"opponent": player2, "step": "protect", "protect_choice": None, "attack_choice": None}
    COMBAT_STATE[player2] = {"opponent": player1, "step": "protect", "protect_choice": None, "attack_choice": None}
    return f"⚔️ **БОЙ НАЧАЛСЯ!**\n\n👤 {player1} vs 👤 {player2}"

def calculate_damage(attack_parts, protect_parts, base_attack, defense):
    total_damage = 0
    for part in attack_parts:
        if part in protect_parts:
            damage = int(base_attack * 0.3) + random.randint(-2, 2)
        else:
            damage = int(base_attack * 1.5) + random.randint(-2, 2)
        if damage < 1:
            damage = 1
        total_damage += damage
    return total_damage

# === ОБРАБОТЧИКИ КОМАНД ===

@bot.message_handler(commands=['start'])
def start_cmd(msg):
    user_id = msg.from_user.id
    username = msg.from_user.username or f"User{user_id}"
    if not get_player(user_id):
        create_player(user_id, username)
        bot.send_message(
            user_id,
            f"🎮 **Добро пожаловать в RPG Дуэль!**\n\n"
            f"Твой ник: @{username}\n"
            f"Ты получил 50 монет и базовое снаряжение.\n"
            f"Используй меню для начала игры.",
            parse_mode='Markdown',
            reply_markup=main_menu()
        )
    else:
        bot.send_message(
            user_id,
            "🎮 **С возвращением, воин!**",
            parse_mode='Markdown',
            reply_markup=main_menu()
        )

# === ОБРАБОТКА КНОПОК ===

@bot.callback_query_handler(func=lambda call: True)
def handle(call):
    user_id = call.from_user.id
    data = call.data
    chat_id = call.message.chat.id
    msg_id = call.message.message_id

    if data == "back_main":
        bot.edit_message_text("🎮 **Главное меню**", chat_id, msg_id, parse_mode='Markdown', reply_markup=main_menu())
        bot.answer_callback_query(call.id)
        return

    if data == "help":
        bot.edit_message_text(
            "📊 **Помощь**\n\n"
            "⚔️ **Дуэль** — найди противника и сразись.\n"
            "🛡️ Защита и атака выбираются по частям тела.\n"
            "💰 За победу даётся опыт и монеты.\n"
            "🏆 Топ показывает лучших игроков.\n"
            "📜 Кланы — создавай и вступай в кланы.\n"
            "🏪 Магазин — покупай снаряжение.",
            chat_id,
            msg_id,
            parse_mode='Markdown',
            reply_markup=main_menu()
        )
        bot.answer_callback_query(call.id)
        return

    if data == "profile":
        stats = get_player_stats(user_id)
        if not stats:
            bot.answer_callback_query(call.id, "❌ Ошибка профиля")
            return
        text = (
            f"👤 **Профиль**\n\n"
            f"Имя: {stats['display_name']}\n"
            f"Уровень: {stats['level']}\n"
            f"Опыт: {stats['exp']}/{stats['exp_to_next']}\n"
            f"❤️ Здоровье: {stats['hp']}/{stats['max_hp']}\n"
            f"⚔️ Атака: {stats['attack']}\n"
            f"🛡️ Защита: {stats['defense']}\n"
            f"💰 Монеты: {stats['coins']}\n"
            f"🗡️ Оружие: {stats['weapon'] or 'Нет'}\n"
            f"🪖 Шлем: {stats['head_armor'] or 'Нет'}\n"
            f"👕 Нагрудник: {stats['chest_armor'] or 'Нет'}\n"
            f"👖 Поножи: {stats['legs_armor'] or 'Нет'}\n"
            f"👢 Ботинки: {stats['boots_armor'] or 'Нет'}"
        )
        bot.edit_message_text(text, chat_id, msg_id, parse_mode='Markdown', reply_markup=main_menu())
        bot.answer_callback_query(call.id)
        return

    if data == "shop":
        cursor.execute("SELECT id, name, type, stat, value, price FROM shop")
        items = cursor.fetchall()
        kb = InlineKeyboardMarkup(row_width=2)
        for item in items:
            kb.add(InlineKeyboardButton(
                f"🛒 {item[1]} ({item[4]}) - {item[5]}💰",
                callback_data=f"buy_{item[0]}"
            ))
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back_main"))
        bot.edit_message_text("🏪 **Магазин**\n\nВыбери предмет для покупки:", chat_id, msg_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("buy_"):
        item_id = int(data.split("_")[1])
        cursor.execute("SELECT name, price, stat, value, type FROM shop WHERE id = ?", (item_id,))
        item = cursor.fetchone()
        if not item:
            bot.answer_callback_query(call.id, "❌ Товар не найден")
            return
        name, price, stat, value, type_ = item
        player = get_player(user_id)
        if player[6] < price:
            bot.answer_callback_query(call.id, f"❌ Не хватает монет! Нужно {price}")
            return
        cursor.execute(f"SELECT {type_} FROM players WHERE user_id = ?", (user_id,))
        current = cursor.fetchone()[0]
        if current:
            cursor.execute("SELECT price FROM shop WHERE name = ?", (current,))
            old_price = cursor.fetchone()[0]
            if old_price:
                cursor.execute("UPDATE players SET coins = coins + ? WHERE user_id = ?", (old_price // 2, user_id))
        cursor.execute(f"UPDATE players SET coins = coins - ?, {type_} = ? WHERE user_id = ?", (price, name, user_id))
        conn.commit()
        bot.answer_callback_query(call.id, f"✅ Куплено: {name}!")
        handle(call)
        return

    if data == "top":
        cursor.execute("SELECT display_name, level, exp, coins FROM players ORDER BY level DESC, exp DESC LIMIT 10")
        top = cursor.fetchall()
        text = "🏆 **Топ игроков**\n\n"
        for i, (name, level, exp, coins) in enumerate(top, 1):
            text += f"{i}. {name} — Уровень {level}, Опыт {exp}, 🪙 {coins}\n"
        bot.edit_message_text(text, chat_id, msg_id, parse_mode='Markdown', reply_markup=main_menu())
        bot.answer_callback_query(call.id)
        return

    if data == "clans":
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("📋 Мои кланы", callback_data="my_clans"),
            InlineKeyboardButton("📜 Список кланов", callback_data="clan_list"),
            InlineKeyboardButton("➕ Создать клан", callback_data="create_clan"),
            InlineKeyboardButton("🔙 Назад", callback_data="back_main")
        )
        bot.edit_message_text("📜 **Кланы**\n\nВыбери действие:", chat_id, msg_id, parse_mode='Markdown', reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data == "my_clans":
        cursor.execute("SELECT clan_id FROM players WHERE user_id = ?", (user_id,))
        clan_id = cursor.fetchone()[0]
        if not clan_id:
            bot.answer_callback_query(call.id, "❌ Ты не состоишь в клане")
            bot.edit_message_text("❌ Ты не состоишь в клане.", chat_id, msg_id, reply_markup=main_menu())
            return
        cursor.execute("SELECT name, leader_id, members FROM clans WHERE id = ?", (clan_id,))
        clan = cursor.fetchone()
        if not clan:
            bot.answer_callback_query(call.id, "❌ Клан не найден")
            return
        members = clan[2].split(",") if clan[2] else []
        text = f"📋 **Клан: {clan[0]}**\n\n👑 Лидер: {clan[1]}\n👥 Участников: {len(members)}\n\nСписок участников:\n"
        for m in members:
            cursor.execute("SELECT display_name FROM players WHERE user_id = ?", (int(m),))
            name = cursor.fetchone()
            if name:
                text += f"- {name[0]}\n"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="clans"))
        bot.edit_message_text(text, chat_id, msg_id, parse_mode='Markdown', reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data == "clan_list":
        cursor.execute("SELECT id, name, leader_id FROM clans ORDER BY id DESC LIMIT 20")
        clans = cursor.fetchall()
        if not clans:
            bot.edit_message_text("📜 **Список кланов**\n\nНет созданных кланов.", chat_id, msg_id, reply_markup=main_menu())
            bot.answer_callback_query(call.id)
            return
        kb = InlineKeyboardMarkup(row_width=1)
        for clan in clans:
            kb.add(InlineKeyboardButton(f"📌 {clan[1]} (лидер: {clan[2]})", callback_data=f"clan_info_{clan[0]}"))
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="clans"))
        bot.edit_message_text("📜 **Список кланов**\n\nВыбери клан для просмотра:", chat_id, msg_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("clan_info_"):
        clan_id = int(data.split("_")[2])
        cursor.execute("SELECT name, leader_id, members FROM clans WHERE id = ?", (clan_id,))
        clan = cursor.fetchone()
        if not clan:
            bot.answer_callback_query(call.id, "❌ Клан не найден")
            return
        members = clan[2].split(",") if clan[2] else []
        text = f"📋 **Клан: {clan[0]}**\n\n👑 Лидер: {clan[1]}\n👥 Участников: {len(members)}\n\nСписок участников:\n"
        for m in members[:10]:
            cursor.execute("SELECT display_name FROM players WHERE user_id = ?", (int(m),))
            name = cursor.fetchone()
            if name:
                text += f"- {name[0]}\n"
        kb = InlineKeyboardMarkup()
        if len(members) < 2:
            kb.add(InlineKeyboardButton("📥 Вступить в клан", callback_data=f"join_clan_{clan_id}"))
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="clan_list"))
        bot.edit_message_text(text, chat_id, msg_id, parse_mode='Markdown', reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("join_clan_"):
        clan_id = int(data.split("_")[2])
        cursor.execute("SELECT members FROM clans WHERE id = ?", (clan_id,))
        members = cursor.fetchone()[0]
        if members and str(user_id) in members.split(","):
            bot.answer_callback_query(call.id, "❌ Ты уже в этом клане")
            return
        new_members = f"{members},{user_id}" if members else str(user_id)
        cursor.execute("UPDATE clans SET members = ? WHERE id = ?", (new_members, clan_id))
        cursor.execute("UPDATE players SET clan_id = ? WHERE user_id = ?", (clan_id, user_id))
        conn.commit()
        bot.answer_callback_query(call.id, "✅ Ты вступил в клан!")
        handle(call)
        return

    if data == "create_clan":
        bot.send_message(chat_id, "📝 **Создание клана**\n\nВведи название клана (от 3 до 15 символов).")
        bot.register_next_step_handler(call.message, create_clan_step)
        bot.answer_callback_query(call.id)
        return

    if data == "duel":
        bot.edit_message_text("⚔️ **Дуэль**\n\nНайди противника и сразись!", chat_id, msg_id, parse_mode='Markdown', reply_markup=duel_menu())
        bot.answer_callback_query(call.id)
        return

    if data == "find_opponent":
        cursor.execute("SELECT user_id, display_name FROM players WHERE user_id != ?", (user_id,))
        opponents = cursor.fetchall()
        if not opponents:
            bot.answer_callback_query(call.id, "❌ Нет других игроков")
            return
        kb = InlineKeyboardMarkup(row_width=1)
        for opp in opponents:
            kb.add(InlineKeyboardButton(f"⚔️ {opp[1]}", callback_data=f"challenge_{opp[0]}"))
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="duel"))
        bot.edit_message_text("⚔️ **Выбери противника:**", chat_id, msg_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("challenge_"):
        opponent_id = int(data.split("_")[1])
        if opponent_id == user_id:
            bot.answer_callback_query(call.id, "❌ Нельзя вызвать себя")
            return
        if user_id in COMBAT_STATE or opponent_id in COMBAT_STATE:
            bot.answer_callback_query(call.id, "❌ Один из игроков уже в бою")
            return
        text = start_battle(user_id, opponent_id)
        bot.send_message(chat_id, text, parse_mode='Markdown')
        ask_protect(user_id, chat_id)
        bot.answer_callback_query(call.id)
        return

    if data == "cancel_duel":
        if user_id in COMBAT_STATE:
            del COMBAT_STATE[user_id]
            bot.answer_callback_query(call.id, "⏹ Бой отменён")
            bot.edit_message_text("⏹ Бой отменён.", chat_id, msg_id, reply_markup=main_menu())
        else:
            bot.answer_callback_query(call.id, "❌ Ты не в бою")
        return

    if data.startswith("protect_"):
        if user_id not in COMBAT_STATE:
            bot.answer_callback_query(call.id, "❌ Ты не в бою")
            return
        choice = data.split("_")[1]
        COMBAT_STATE[user_id]["protect_choice"] = choice
        opponent_id = COMBAT_STATE[user_id]["opponent"]
        if COMBAT_STATE[opponent_id]["protect_choice"]:
            ask_attack(user_id, chat_id)
            ask_attack(opponent_id, opponent_id)
            bot.answer_callback_query(call.id, "✅ Защита выбрана")
        else:
            bot.answer_callback_query(call.id, "✅ Защита выбрана. Жди противника.")
        return

    if data.startswith("attack_"):
        if user_id not in COMBAT_STATE:
            bot.answer_callback_query(call.id, "❌ Ты не в бою")
            return
        choice = data.split("_")[1]
        COMBAT_STATE[user_id]["attack_choice"] = choice
        opponent_id = COMBAT_STATE[user_id]["opponent"]
        if COMBAT_STATE[opponent_id]["attack_choice"]:
            resolve_battle(user_id, opponent_id, chat_id)
        else:
            bot.answer_callback_query(call.id, "✅ Атака выбрана. Жди противника.")
        return

def ask_protect(user_id, chat_id):
    kb = InlineKeyboardMarkup(row_width=1)
    for combo in PROTECT_COMBOS:
        kb.add(InlineKeyboardButton(f"🛡️ {combo.replace('_', 
