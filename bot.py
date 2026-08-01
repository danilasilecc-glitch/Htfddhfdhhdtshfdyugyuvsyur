import os
import time
import sqlite3
import random
import threading
from datetime import datetime, timedelta
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# === КОНФИГ ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан!")

bot = telebot.TeleBot(BOT_TOKEN)

# === БАЗА ДАННЫХ ===
conn = sqlite3.connect("collection_bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS players (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    stars INTEGER DEFAULT 0,
    last_package_time INTEGER DEFAULT 0,
    inventory TEXT DEFAULT '',
    trade_lock INTEGER DEFAULT 0
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS auctions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id INTEGER,
    item_name TEXT,
    item_rarity TEXT,
    current_bid INTEGER,
    bidder_id INTEGER DEFAULT NULL,
    end_time INTEGER,
    active INTEGER DEFAULT 1
)
''')

# === 100+ ПРЕДМЕТОВ (с редкостью и описанием) ===
ITEMS = {
    "common": [
        {"name": "Гнилой картофель", "desc": "Сгнил до неузнаваемости. Пахнет ужасно."},
        {"name": "Дырявый носок", "desc": "От старого рыцаря. Ещё теплый."},
        {"name": "Ржавый гвоздь", "desc": "Может пригодиться... или нет."},
        {"name": "Обгрызок карандаша", "desc": "Кто-то очень нервничал."},
        {"name": "Камень с дыркой", "desc": "Редкость? Нет, просто камень."},
        {"name": "Сломанная ложка", "desc": "Для супа уже не годится."},
        {"name": "Пыльная книга", "desc": "Никто не откроет."},
        {"name": "Пустая банка", "desc": "Из-под тушёнки."},
        {"name": "Рваный шнурок", "desc": "От ботинка, который уже выбросили."},
        {"name": "Кусок кирпича", "desc": "От старого дома."},
        {"name": "Мятая монета", "desc": "Даже хлеба не купить."},
        {"name": "Сухой лист", "desc": "Был с дерева."},
        {"name": "Клочок бумаги", "desc": "На нём что-то написано, но стёрлось."},
        {"name": "Стеклянная бутылка", "desc": "Из-под лимонада."},
        {"name": "Резиновая утка", "desc": "Совсем не смешная."},
        {"name": "Старый ботинок", "desc": "Правый."},
        {"name": "Металлическая гайка", "desc": "От трактора."},
        {"name": "Кусок мела", "desc": "Исписан до крошки."},
        {"name": "Обломок расчёски", "desc": "Кому теперь расчёсываться?"},
        {"name": "Пластиковая вилка", "desc": "Одноразовая, но на века."},
        {"name": "Кусок ваты", "desc": "Из старой подушки."},
        {"name": "Глиняный черепок", "desc": "От древней цивилизации."},
        {"name": "Исписанный стикер", "desc": "Список покупок 2019 года."},
        {"name": "Бейсболка без козырька", "desc": "Солнце теперь не остановить."},
        {"name": "Колесо от тележки", "desc": "Скрипит."},
        {"name": "Кусок проволоки", "desc": "Можно скрутить."},
        {"name": "Гвоздь с кривой шляпкой", "desc": "Бракованный."},
        {"name": "Засохшая краска", "desc": "Цвет — бежевый."},
        {"name": "Чашка без ручки", "desc": "Горячий чай не взять."},
        {"name": "Сломанный зонт", "desc": "Дождя не боится — он уже сломан."},
        {"name": "Мятый конверт", "desc": "Без письма."},
        {"name": "Лампочка накаливания", "desc": "Перегорела."},
        {"name": "Ржавый болт", "desc": "От старого моста."},
        {"name": "Кусок ткани", "desc": "От флага, который никто не поднимал."},
        {"name": "Стеклянный шарик", "desc": "Для игры в «камешки»."},
    ],
    "uncommon": [
        {"name": "Золотая монета", "desc": "Блестит, но не греет."},
        {"name": "Серебряная ложка", "desc": "Для королевского супа."},
        {"name": "Старый компас", "desc": "Показывает на север, но иногда врёт."},
        {"name": "Медальон с фото", "desc": "Неизвестный человек."},
        {"name": "Кожаный кошелёк", "desc": "Пустой, но красивый."},
        {"name": "Фарфоровая кукла", "desc": "Смотрит в душу."},
        {"name": "Шахматная фигура", "desc": "Чёрный ферзь."},
        {"name": "Книга рекордов", "desc": "Издание 1985 года."},
        {"name": "Набор отмычек", "desc": "Для любопытных."},
        {"name": "Старый револьвер", "desc": "Заряжен? Неизвестно."},
        {"name": "Золотой зуб", "desc": "Чей-то."},
        {"name": "Карта сокровищ", "desc": "Нарисована на салфетке."},
        {"name": "Бинокль", "desc": "В одном окуляре трещина."},
    ],
    "rare": [
        {"name": "Меч героя", "desc": "Убил не одного дракона."},
        {"name": "Магический кристалл", "desc": "Исполняет одно желание."},
        {"name": "Щит короля", "desc": "С выгравированным гербом."},
        {"name": "Кольцо власти", "desc": "Не для слабых."},
        {"name": "Зелье бессмертия", "desc": "На 5 минут."},
        {"name": "Плащ невидимости", "desc": "Работает, если никто не смотрит."},
        {"name": "Глаз дракона", "desc": "Светится в темноте."},
        {"name": "Книга проклятий", "desc": "Читать с осторожностью."},
        {"name": "Лунный камень", "desc": "Отражает лунный свет."},
        {"name": "Корона императора", "desc": "Давит на голову."},
        {"name": "Посох мага", "desc": "С наконечником из обсидиана."},
        {"name": "Золотое яблоко", "desc": "Выглядит вкусно."},
        {"name": "Крылья ангела", "desc": "Перья."},
        {"name": "Амулет с рубином", "desc": "Защищает от сглаза."},
        {"name": "Артефакт времени", "desc": "Останавливает время на мгновение."},
    ],
    "legendary": [
        {"name": "Экскалибур", "desc": "Вытащить может только избранный."},
        {"name": "Слеза бога", "desc": "Говорят, она может воскресить."},
        {"name": "Трон из костей", "desc": "Сильный, но холодный."},
        {"name": "Кубок Грааля", "desc": "Даёт мудрость."},
        {"name": "Молот Тора", "desc": "Кто поднимет — тот достоин."},
        {"name": "Феникс", "desc": "Воскреснет после смерти."},
        {"name": "Ключ от Рая", "desc": "Куда-то открывает."},
        {"name": "Кровь дракона", "desc": "В бутылочке."},
        {"name": "Глаз Всевидящего", "desc": "Видит сквозь стены."},
        {"name": "Бесконечный пергамент", "desc": "На нём можно писать вечно."},
    ],
    "mythic": [
        {"name": "Ban Hammer", "desc": "Может ограбить любого и получить его предмет."},
        {"name": "Сердце вселенной", "desc": "Даёт бесконечную силу."},
        {"name": "Корона хаоса", "desc": "Переворачивает реальность."},
        {"name": "Душа мира", "desc": "Содержит память всех времён."},
    ]
}

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
def get_player(user_id):
    cursor.execute("SELECT * FROM players WHERE user_id = ?", (user_id,))
    return cursor.fetchone()

def create_player(user_id, username):
    cursor.execute("INSERT INTO players (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()

def get_inventory(user_id):
    player = get_player(user_id)
    if not player:
        return []
    inv = player[5]
    if inv == "":
        return []
    return inv.split(",")

def add_item(user_id, item_name):
    inv = get_inventory(user_id)
    inv.append(item_name)
    cursor.execute("UPDATE players SET inventory = ? WHERE user_id = ?", (",".join(inv), user_id))
    conn.commit()

def remove_item(user_id, item_name):
    inv = get_inventory(user_id)
    if item_name in inv:
        inv.remove(item_name)
        cursor.execute("UPDATE players SET inventory = ? WHERE user_id = ?", (",".join(inv), user_id))
        conn.commit()
        return True
    return False

def get_item_rarity(item_name):
    for rarity, items in ITEMS.items():
        for i in items:
            if i["name"] == item_name:
                return rarity
    return None

def get_item_desc(item_name):
    for rarity, items in ITEMS.items():
        for i in items:
            if i["name"] == item_name:
                return i["desc"]
    return "Описание отсутствует."

def get_random_item():
    # Шансы: common 50%, uncommon 25%, rare 15%, legendary 8%, mythic 2%
    roll = random.randint(1, 100)
    if roll <= 50:
        rarity = "common"
    elif roll <= 75:
        rarity = "uncommon"
    elif roll <= 90:
        rarity = "rare"
    elif roll <= 98:
        rarity = "legendary"
    else:
        rarity = "mythic"
    return random.choice(ITEMS[rarity])

def get_item_value(item_name):
    rarity = get_item_rarity(item_name)
    values = {"common": 10, "uncommon": 50, "rare": 200, "legendary": 500, "mythic": 1000}
    return values.get(rarity, 0)

# === КЛАВИАТУРЫ ===
def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📦 Открыть посылку", callback_data="open_package"),
        InlineKeyboardButton("🎒 Инвентарь", callback_data="inventory"),
        InlineKeyboardButton("🏆 Топ богатых", callback_data="top"),
        InlineKeyboardButton("🏪 Магазин", callback_data="shop"),
        InlineKeyboardButton("⚖️ Аукцион", callback_data="auction"),
        InlineKeyboardButton("📞 Связь", callback_data="support")
    )
    return kb

# === КОМАНДЫ ===
@bot.message_handler(commands=['start'])
def start_cmd(msg):
    user_id = msg.from_user.id
    username = msg.from_user.username or f"User{user_id}"
    if not get_player(user_id):
        create_player(user_id, username)
    bot.send_message(
        user_id,
        "🎁 **Добро пожаловать в коллекционный бот!**\n\n"
        "Каждые 12 часов ты можешь открыть посылку и получить случайный предмет.\n"
        "Собирай коллекцию, торгуйся на аукционе и становись самым богатым!",
        parse_mode='Markdown',
        reply_markup=main_menu()
    )

@bot.callback_query_handler(func=lambda call: True)
def handle(call):
    user_id = call.from_user.id
    data = call.data
    chat_id = call.message.chat.id
    msg_id = call.message.message_id

    if data == "support":
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📢 Перейти в канал", url="https://t.me/TeamSearchChannel"))
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back_main"))
        bot.edit_message_text("📞 **Связь с поддержкой**\n\nПерейди в наш канал:", chat_id, msg_id, parse_mode='Markdown', reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data == "back_main":
        bot.edit_message_text("🎁 **Главное меню**", chat_id, msg_id, parse_mode='Markdown', reply_markup=main_menu())
        bot.answer_callback_query(call.id)
        return

    if data == "open_package":
        player = get_player(user_id)
        if not player:
            bot.answer_callback_query(call.id, "❌ Ошибка")
            return
        last_time = player[4]
        now = int(time.time())
        if now - last_time < 43200:  # 12 часов
            remaining = 43200 - (now - last_time)
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            bot.answer_callback_query(call.id, f"⏳ Жди {hours}ч {minutes}мин до следующей посылки")
            return
        item = get_random_item()
        add_item(user_id, item["name"])
        cursor.execute("UPDATE players SET last_package_time = ? WHERE user_id = ?", (now, user_id))
        conn.commit()
        bot.edit_message_text(
            f"📦 **Ты открыл посылку!**\n\n"
            f"🎁 {item['name']} (Редкость: {get_item_rarity(item['name'])})\n"
            f"📖 {item['desc']}",
            chat_id, msg_id, parse_mode='Markdown', reply_markup=main_menu()
        )
        bot.answer_callback_query(call.id)
        return

    if data == "inventory":
        inv = get_inventory(user_id)
        if not inv:
            bot.edit_message_text("🎒 **Твой инвентарь пуст**", chat_id, msg_id, parse_mode='Markdown', reply_markup=main_menu())
            bot.answer_callback_query(call.id)
            return
        text = "🎒 **Твой инвентарь**\n\n"
        for item in inv:
            rarity = get_item_rarity(item)
            desc = get_item_desc(item)
            text += f"🟢 {item} (Редкость: {rarity})\n   {desc}\n\n"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back_main"))
        bot.edit_message_text(text, chat_id, msg_id, parse_mode='Markdown', reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data == "top":
        cursor.execute("SELECT username, stars FROM players ORDER BY stars DESC LIMIT 10")
        top = cursor.fetchall()
        text = "🏆 **Топ богатых игроков**\n\n"
        for i, (username, stars) in enumerate(top, 1):
            text += f"{i}. @{username} — {stars} ⭐\n"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back_main"))
        bot.edit_message_text(text, chat_id, msg_id, parse_mode='Markdown', reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data == "shop":
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("⚡ Открыть посылку (15 ⭐)", callback_data="buy_package"),
            InlineKeyboardButton("🔨 Ban Hammer (100 ⭐)", callback_data="buy_hammer"),
            InlineKeyboardButton("🔙 Назад", callback_data="back_main")
        )
        bot.edit_message_text("🏪 **Магазин**\n\nВыбери, что купить:", chat_id, msg_id, parse_mode='Markdown', reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data == "buy_package":
        player = get_player(user_id)
        if player[3] < 15:
            bot.answer_callback_query(call.id, "❌ Не хватает звёзд! Нужно 15")
            return
        cursor.execute("UPDATE players SET stars = stars - 15 WHERE user_id = ?", (user_id,))
        item = get_random_item()
        add_item(user_id, item["name"])
        conn.commit()
        bot.edit_message_text(
            f"⚡ **Ты купил посылку!**\n\n"
            f"🎁 {item['name']} (Редкость: {get_item_rarity(item['name'])})\n"
            f"📖 {item['desc']}",
            chat_id, msg_id, parse_mode='Markdown', reply_markup=main_menu()
        )
        bot.answer_callback_query(call.id)
        return

    if data == "buy_hammer":
        player = get_player(user_id)
        if player[3] < 100:
            bot.answer_callback_query(call.id, "❌ Не хватает звёзд! Нужно 100")
            return
        if "Ban Hammer" in get_inventory(user_id):
            bot.answer_callback_query(call.id, "❌ У тебя уже есть Ban Hammer")
            return
        cursor.execute("UPDATE players SET stars = stars - 100 WHERE user_id = ?", (user_id,))
        add_item(user_id, "Ban Hammer")
        conn.commit()
        bot.edit_message_text(
            "🔨 **Ты купил Ban Hammer!**\n\n"
            "Теперь ты можешь ограбить любого игрока и получить его случайный предмет.",
            chat_id, msg_id, parse_mode='Markdown', reply_markup=main_menu()
        )
        bot.answer_callback_query(call.id)
        return

    # === АУКЦИОН ===
    if data == "auction":
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("📋 Список лотов", callback_data="auction_list"),
            InlineKeyboardButton("➕ Выставить лот", callback_data="auction_add"),
            InlineKeyboardButton("🔙 Назад", callback_data="back_main")
        )
        bot.edit_message_text("⚖️ **Аукцион**\n\nВыбери действие:", chat_id, msg_id, parse_mode='Markdown', reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data == "auction_list":
        cursor.execute("SELECT id, seller_id, item_name, current_bid, bidder_id, end_time FROM auctions WHERE active = 1")
        auctions = cursor.fetchall()
        if not auctions:
            bot.edit_message_text("📋 **Аукцион пуст**", chat_id, msg_id, parse_mode='Markdown', reply_markup=main_menu())
            bot.answer_callback_query(call.id)
            return
        text = "📋 **Активные лоты**\n\n"
        for auction in auctions:
            seller = get_player(auction[1])
            seller_name = seller[1] if seller else "Unknown"
            bidder = get_player(auction[4]) if auction[4] else None
            bidder_name = bidder[1] if bidder else "Нет ставок"
            time_left = auction[5] - int(time.time())
            hours = time_left // 3600
            minutes = (time_left % 3600) // 60
            text += f"🟢 {auction[2]} (Ставка: {auction[3]} ⭐)\n"
            text += f"   Продавец: @{seller_name}\n"
            text += f"   Ставка: @{bidder_name}\n"
            text += f"   Осталось: {hours}ч {minutes}мин\n\n"
        kb = InlineKeyboardMarkup(row_width=1)
        for auction in auctions:
            kb.add(InlineKeyboardButton(f"⚖️ {auction[2]}", callback_data=f"bid_{auction[0]}"))
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="auction"))
        bot.edit_message_text(text, chat_id, msg_id, parse_mode='Markdown', reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("bid_"):
        auction_id = int(data.split("_")[1])
        cursor.execute("SELECT seller_id, item_name, current_bid, bidder_id FROM auctions WHERE id = ? AND active = 1", (auction_id,))
        auction = cursor.fetchone()
        if not auction:
            bot.answer_callback_query(call.id, "❌ Лот не найден")
            return
        # Ставка +10
        new_bid = auction[2] + 10
        cursor.execute("UPDATE auctions SET current_bid = ?, bidder_id = ? WHERE id = ?", (new_bid, user_id, auction_id))
        conn.commit()
        bot.answer_callback_query(call.id, f"✅ Ваша ставка {new_bid} ⭐ принята!")
        bot.edit_message_text("⚖️ **Аукцион**\n\nВаша ставка принята!", chat_id, msg_id, parse_mode='Markdown', reply_markup=main_menu())
        return

    if data == "auction_add":
        inv = get_inventory(user_id)
        if not inv:
            bot.answer_callback_query(call.id, "❌ У тебя нет предметов для выставления")
            return
        kb = InlineKeyboardMarkup(row_width=1)
        for item in inv:
            kb.add(InlineKeyboardButton(f"📦 {item}", callback_data=f"sell_{item}"))
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="auction"))
        bot.edit_message_text("➕ **Выбери предмет для продажи:**", chat_id, msg_id, parse_mode='Markdown', reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("sell_"):
        item_name = data.split("_", 1)[1]
        if not remove_item(user_id, item_name):
            bot.answer_callback_query(call.id, "❌ Ошибка")
            return
        start_price = get_item_value(item_name)
        end_time = int(time.time()) + 86400 * 3  # 3 дня
        cursor.execute(
            "INSERT INTO auctions (seller_id, item_name, current_bid, end_time) VALUES (?, ?, ?, ?)",
            (user_id, item_name, start_price, end_time)
        )
        conn.commit()
        bot.answer_callback_query(call.id, f"✅ {item_name} выставлен на аукцион за {start_price} ⭐")
        bot.edit_message_text("⚖️ **Аукцион**\n\nПредмет выставлен!", chat_id, msg_id, parse_mode='Markdown', reply_markup=main_menu())
        return

    # === BAN HAMMER ===
    if data == "use_hammer":
        if "Ban Hammer" not in get_inventory(user_id):
            bot.answer_callback_query(call.id, "❌ У тебя нет Ban Hammer!")
            return
        cursor.execute("SELECT user_id, username FROM players WHERE user_id != ?", (user_id,))
        players = cursor.fetchall()
        if not players:
            bot.answer_callback_query(call.id, "❌ Нет других игроков")
            return
        kb = InlineKeyboardMarkup(row_width=1)
        for player in players:
            kb.add(InlineKeyboardButton(f"🔨 @{player[1]}", callback_data=f"rob_{player[0]}"))
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back_main"))
        bot.edit_message_text("🔨 **Выбери жертву:**", chat_id, msg_id, parse_mode='Markdown', reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("rob_"):
        target_id = int(data.split("_")[1])
        target_inv = get_inventory(target_id)
        if not target_inv:
            bot.answer_callback_query(call.id, "❌ У игрока нет предметов")
            return
        item = random.choice(target_inv)
        remove_item(target_id, item)
        add_item(user_id, item)
        remove_item(user_id, "Ban Hammer")  # Одноразовый
        bot.edit_message_text(
            f"🔨 **Ты ограбил @{get_player(target_id)[1]}!**\n\n"
            f"🎁 Ты получил: {item}",
            chat_id, msg_id, parse_mode='Markdown', reply_markup=main_menu()
        )
        bot.answer_callback_query(call.id)
        return

# === АВТО-ПИНГ ===
def keep_alive():
    while True:
        time.sleep(300)
        try:
            bot.get_me()
            print("✅ Пинг успешен")
        except Exception as e:
            print(f"❌ Ошибка пинга: {e}")

threading.Thread(target=keep_alive, daemon=True).start()

# === ЗАПУСК ===
print("🚀 Бот-коллекция запущен!")
bot.infinity_polling()