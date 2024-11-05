import os
from datetime import datetime
from pymongo import MongoClient
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import json

# הגדרות קבועות ומידע חסוי ממשתני סביבה
TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/mydatabase")


# התחברות למסד הנתונים
print(f"Connecting to MongoDB at {MONGO_URI}")
client = MongoClient(MONGO_URI)
db = client['poker_bot']
players_collection = db['players']
games_collection = db['games']
print(f"Db connection established")

# ==========================
# פונקציות עזר
# ==========================

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

def get_summary():
    """ פונקציה שמחזירה את מספר המשחקים, הצ'אטים והשחקנים """
    total_games = games_collection.count_documents({})
    total_chats = len(games_collection.distinct("chat_id"))
    total_players = players_collection.count_documents({})
    return {
        "total_games": total_games,
        "total_chats": total_chats,
        "total_players": total_players
    }

class SummaryHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/summary":
            summary_data = get_summary()
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(summary_data).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

def start_summary_server():
    server_address = ('', 8000)
    httpd = HTTPServer(server_address, SummaryHandler)
    print("Starting summary server on port 8000")
    httpd.serve_forever()

# Run the dummy server in a separate thread
print("Starting dummy server thread")
threading.Thread(target=start_summary_server, daemon=True).start()
print("Dummy server thread started")

def initialize_game_start_date_if_needed(game_id):
    """ מעדכנת את תאריך ההתחלה של המשחק אם לא הוגדר """
    active_game = games_collection.find_one({"_id": game_id})
    if active_game and active_game["start_date"] is None:
        games_collection.update_one(
            {"_id": game_id},
            {"$set": {"start_date": datetime.now()}}
        )
        
def get_or_create_active_game(chat_id):
    """ מחזירה את game_id של המשחק הפעיל בצ'אט או יוצרת חדש אם אין כזה """
    active_game = games_collection.find_one({"chat_id": chat_id, "status": "active"})
    if not active_game:
        game_id = games_collection.insert_one({
            "chat_id": chat_id,
            "start_date": None,
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

    # קריאה לפונקציית העזר לעדכון תאריך ההתחלה אם זהו הקנייה הראשונה
    initialize_game_start_date_if_needed(game_id)
    
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
    
    # שמירת דירוג המשחק במסד הנתונים
    sorted_players_data = sorted(players_data, key=lambda x: x['amount'], reverse=True)
    games_collection.update_one(
        {"_id": game_id},
        {"$set": {"ranking": sorted_players_data}}
    )
    
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
    count = 1
    for game in games:
        start_date = game["start_date"].strftime("%Y-%m-%d %H:%M")
        end_date = game.get("end_date", "לא ידוע").strftime("%Y-%m-%d %H:%M") if game.get("end_date") else "לא ידוע"
        message += f"\nמשחק: {count}\nתאריך התחלה: {start_date}\nתאריך סיום: {end_date}\n"
        count += 1
        # הצגת דירוג אם קיים
        if 'ranking' in game:
            message += "דירוג:\n"
            for player_data in game['ranking']:
                name = player_data['name']
                amount = player_data['amount']
                message += f"{name} {'הרוויח' if amount > 0 else 'הפסיד'} {abs(amount)} ₪\n"
        else:
            message += "דירוג לא זמין למשחק זה.\n"
        
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

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    players_stats = []

    # שליפת כל המשחקים בצ'אט זה
    games = games_collection.find({"chat_id": chat_id})
    player_summary = {}

    # מיפוי רווחים והפסדים עבור כל שחקן בכל המשחקים
    for game in games:
        game_ranking = []
        
        for player in players_collection.find({"chat_id": chat_id, "game_id": game["_id"]}):
            name = player['name']
            chips_bought = player.get('chips_bought', 0)
            chips_end = player.get('chips_end', 0)
            profit = chips_end - chips_bought
            game_ranking.append((name, profit))

            if name not in player_summary:
                player_summary[name] = {
                    "total_profit": 0,
                    "games_played": 0,
                    "first_place_wins": 0,
                    "total_rank": 0,
                }
            player_summary[name]["total_profit"] += profit
            player_summary[name]["games_played"] += 1
        
        # מיון הדירוג של השחקנים במשחק זה לפי הרווח
        game_ranking.sort(key=lambda x: x[1], reverse=True)

        # חישוב מיקום לכל שחקן במשחק הנוכחי
        for rank, (name, profit) in enumerate(game_ranking, start=1):
            player_summary[name]["total_rank"] += rank
            if rank == 1:
                player_summary[name]["first_place_wins"] += 1

    # בניית הפלט לכל שחקן בנפרד
    message = "סטטיסטיקות כלליות לשחקנים:\n"
    for name, data in player_summary.items():
        total_profit = data["total_profit"]
        games_played = data["games_played"]
        first_place_wins = data["first_place_wins"]
        average_rank = data["total_rank"] / games_played if games_played > 0 else 0

        message += f"\nסטטיסטיקות של {name}:\n"
        message += f"סך רווחים/הפסדים: {total_profit} ₪\n"
        message += f"מספר משחקים: {games_played}\n"
        message += f"מספר פעמים במקום ראשון: {first_place_wins}\n"
        message += f"מיקום ממוצע: {average_rank:.2f}\n"

    # שליחת הפלט למשתמש
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
        CommandHandler("history", history),
        CommandHandler("stats", stats)
    ]
    
    for handler in handlers:
        application.add_handler(handler)

    # Define error handler
    def error_handler(update: Update, context: CallbackContext):
        try:
            raise context.error
        except telegram.error.Conflict:
            print("Conflict error: Another instance is likely running.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}", exc_info=True)
    
    # Add the error handler to the application
    application.add_error_handler(error_handler)
    
    print("Bot polling")
    application.run_polling(poll_interval=2.0, timeout=10)
    
if __name__ == '__main__':
    main()
