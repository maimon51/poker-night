import os
from datetime import datetime
from pymongo import MongoClient
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# הגדרות קבועות ומידע חסוי ממשתני סביבה
TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/mydatabase")

# התחברות למסד הנתונים
client = MongoClient(MONGO_URI)
db = client['poker_bot']
players_collection = db['players']
games_collection = db['games']

print(f"Connected to MongoDB at {MONGO_URI}")

# ==========================
# פונקציות עזר
# ==========================

def get_or_create_active_game(chat_id):
    """ מחזירה את game_id של המשחק הפעיל בצ'אט או יוצרת חדש אם אין כזה """
    active_game = games_collection.find_one({"chat_id": chat_id, "status": "active"})
    if not active_game:
        game_id = games_collection.insert_one({
            "chat_id": chat_id,
            "start_date": datetime.now(),
            "end_date": None,
            "status": "active"
        }).inserted_id
    else:
        game_id = active_game["_id"]
    return game_id


def end_current_game(chat_id):
    """ מסמנת את המשחק הפעיל כלא פעיל ומעדכנת תאריך סיום """
    games_collection.update_one(
        {"chat_id": chat_id, "status": "active"},
        {"$set": {"status": "inactive", "end_date": datetime.now()}}
    )

def get_player_data(chat_id, game_id, name):
    """ מחזירה נתוני שחקן במשחק הנוכחי אם קיים """
    return players_collection.find_one({"chat_id": chat_id, "game_id": game_id, "name": name})

async def send_message(update, message):
    """ שולחת הודעה לצ'אט הנוכחי """
    await update.message.reply_text(message)

# ==========================
# פקודות בוט
# ==========================

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ הוספת שחקן או עדכון קניית צ'יפים עבור שחקן קיים """
    chat_id = update.effective_chat.id
    game_id = get_or_create_active_game(chat_id)

    try:
        name, chips_bought = context.args[0], int(context.args[1])
        player = get_player_data(chat_id, game_id, name)

        if player:
            chips_total = chips_bought + player['chips_bought']
            players_collection.update_one(
                {"_id": player["_id"]},
                {"$set": {"chips_bought": chips_total}}
            )
            message = f"שחקן {name} קיים, נוספו לו {chips_bought} צ'יפים (סה\"כ {chips_total})"
        else:
            players_collection.insert_one({
                "chat_id": chat_id,
                "game_id": game_id,
                "name": name,
                "chips_bought": chips_bought,
                "chips_end": 0
            })
            message = f"שחקן {name} נוסף עם {chips_bought} צ'יפים"
        await send_message(update, message)
    except (IndexError, ValueError):
        await send_message(update, "שימוש: /buy <שם> <כמות צ'יפים>")

async def end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ עדכון צ'יפים סופי עבור שחקן """
    chat_id = update.effective_chat.id
    game_id = get_or_create_active_game(chat_id)

    try:
        name, chips_end = context.args[0], int(context.args[1])
        player = get_player_data(chat_id, game_id, name)

        if player:
            players_collection.update_one(
                {"_id": player["_id"]},
                {"$set": {"chips_end": chips_end}}
            )
            message = f"שחקן {name} סיים עם {chips_end} צ'יפים"
        else:
            message = f"שחקן {name} לא קיים"
        await send_message(update, message)
    except (IndexError, ValueError):
        await send_message(update, "שימוש: /end <שם> <כמות צ'יפים>")

async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ מספקת סיכום של המשחק כולל חישוב רווחים והפסדים """
    chat_id = update.effective_chat.id
    game_id = get_or_create_active_game(chat_id)

    if len(context.args) == 0:
        await send_message(update, "שימוש: /summary <יחס ההמרה>")
        return

    ratio = float(context.args[0])
    message = f'סיכום המשחק:\nיחס ההמרה ₪{ratio}/1000\n'
    players_data = []
    
    # חישוב רווחים והפסדים
    for player in players_collection.find({"chat_id": chat_id, "game_id": game_id}):
        name = player['name']
        chips_bought, chips_end = player.get('chips_bought'), player.get('chips_end')
        
        if chips_bought is None or chips_end is None:
            await send_message(update, f"שחקן {name} עדיין לא השלים את הנתונים")
            return
        
        difference = chips_end - chips_bought
        amount = difference * (ratio / 1000)
        players_data.append({'name': name, 'amount': amount})

        message += f"{name} צריך {'לקבל' if amount > 0 else 'לשלם'} {abs(amount)} ₪\n"
    
    # העברות כספיות
    transfer_message = "\nהעברות כספיות:\n"
    debtors = [p for p in players_data if p['amount'] < 0]
    creditors = [p for p in players_data if p['amount'] > 0]
    
    while debtors and creditors:
        debtor, creditor = debtors.pop(), creditors.pop()
        transfer_amount = min(abs(debtor['amount']), creditor['amount'])
        transfer_message += f"{debtor['name']} צריך להעביר {transfer_amount} ₪ ל{creditor['name']}\n"
        debtor['amount'] += transfer_amount
        creditor['amount'] -= transfer_amount

        if debtor['amount'] < 0: debtors.append(debtor)
        if creditor['amount'] > 0: creditors.append(creditor)

    await send_message(update, message + transfer_message)

async def endgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game_id = games_collection.find_one({"chat_id": chat_id, "status": "active"})
    
    if not game_id:
        await update.message.reply_text("אין משחק פעיל לסיים.")
        return
    
    # סיום המשחק הפעיל
    end_current_game(chat_id)
    await update.message.reply_text("המשחק הנוכחי הסתיים ונשמר בהיסטוריה.")

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    games = games_collection.find({"chat_id": chat_id}).sort("start_date", -1)
    message = "היסטוריית משחקים:\n"
    for game in games:
        start_date = game["start_date"].strftime("%Y-%m-%d %H:%M")
        end_date = game.get("end_date", "לא ידוע").strftime("%Y-%m-%d %H:%M") if game.get("end_date") else "לא ידוע"
        message += f"\nמזהה משחק: {game['_id']}\nתאריך התחלה: {start_date}\nתאריך סיום: {end_date}\n"
        for player in players_collection.find({"chat_id": chat_id, "game_id": game["_id"]}):
            message += f"שחקן {player['name']} קנה {player['chips_bought']} צ'יפים וסיים עם {player['chips_end']} צ'יפים\n"
    await update.message.reply_text(message)
        
async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    game_id = get_or_create_active_game(chat_id)

    message = 'מחיקת המשחק:\n'

    # מחיקת שחקנים בצ'אט הנוכחי בלבד
    result = players_collection.delete_many({"chat_id": chat_id, "game_id": game_id})
    message += f"{result.deleted_count} שחקנים נמחקו\n"
    await update.message.reply_text(message)

async def debug(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    game_id = get_or_create_active_game(chat_id)
    message = 'נתוני המשחק:\n'

    # הצגת נתוני שחקנים בצ'אט הנוכחי בלבד
    for player in players_collection.find({"chat_id": chat_id, "game_id": game_id}):
        message += f"שחקן {player['name']} קנה {player['chips_bought']} צ'יפים וסיים עם {player['chips_end']} צ'יפים\n"
    await update.message.reply_text(message)
    
# הוספת הגדרות ל-main
def main():
    application = Application.builder().token(TOKEN).build()
    handlers = [
        CommandHandler("buy", buy),
        CommandHandler("end", end),
        CommandHandler("summary", summary),
        CommandHandler("clear", clear),
        CommandHandler("debug", debug),
        CommandHandler("endgame", endgame),
        CommandHandler("history", history)
    ]
    
    for handler in handlers:
        application.add_handler(handler)

    print("Bot polling")
    application.run_polling(poll_interval=2.0, timeout=10)

if __name__ == '__main__':
    main()
