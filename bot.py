from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from pymongo import MongoClient

# הגדרת הטוקן שלך
TOKEN = '7401130201:AAEBfejEiECuujHRrzdPferHx4xuFzdfsMQ'

# התחברות למסד הנתונים MongoDB
client = MongoClient('mongodb://root:rootroot@localhost:27017/')
db = client['poker_bot']
players_collection = db['players']

# הגדרת הפקודה להוספת שחקן חדש וקניית צ'יפים
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        name = context.args[0]
        chips_bought = int(context.args[1])

        found = players_collection.find_one({"name": name})
        if found:
            # עדכון כמות הצ'יפים שנרכשו
            chips_exist = found['chips_bought']
            chips_total = chips_bought + chips_exist
            message = f"שחקן {name} קיים ונוספו לו {chips_bought} צ'יפים, סה\"כ {chips_total} צ'יפים"
            # הוספת השחקן למסד הנתונים
            players_collection.update_one(
                {"name": name},
                {"$set": {"chips_bought": chips_total, "chips_end": 0}},
                upsert=True
            )
            await update.message.reply_text(message)
        else:
            # הוספת השחקן למסד הנתונים
            players_collection.update_one(
                {"name": name},
                {"$set": {"chips_bought": chips_bought, "chips_end": 0}},
                upsert=True
            )

            await update.message.reply_text(f"שחקן {name} נוסף עם {chips_bought} צ'יפים")
    except (IndexError, ValueError):
        await update.message.reply_text("שימוש: /buy <שם> <כמות צ'יפים>")

# פקודה לעדכון כמות הצ'יפים הסופית
async def end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        name = context.args[0]
        chips_end = int(context.args[1])
        found = players_collection.find_one({"name": name})
        if found:
            # עדכון השחקן במסד הנתונים
            players_collection.update_one(
                {"name": name},
                {"$set": {"chips_end": chips_end}}
            )

            await update.message.reply_text(f"שחקן {name} סיים עם {chips_end} צ'יפים")
        else:
            await update.message.reply_text(f"שחקן {name} לא קיים")
            
    except (IndexError, ValueError):
        await update.message.reply_text("שימוש: /end <שם> <כמות צ'יפים>")

# פקודה לסיכום המשחק
async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) == 0:
        await update.message.reply_text("שימוש: /summary <יחס ההמרה>")
        return
    
    ratio = float(context.args[0])  # כמה עולה 1000 צ'יפים

    message = 'סיכום המשחק:\n'
    message += f"יחס ההמרה ₪/1000: {ratio}\n"

    # משתנים לצורך בדיקת כמות הצ'יפים הכוללת
    total_chips_bought = 0
    total_chips_end = 0
    players_data = []

    # חישוב רווחים והפסדים
    for player in players_collection.find():
        name = player['name']
        chips_bought = player.get('chips_bought')
        chips_end = player.get('chips_end')
        
        # בדיקה שכל שחקן סיים את המשחק
        if chips_bought is None or chips_end is None:
            await update.message.reply_text(f"שחקן {name} עדיין לא השלים את הנתונים")
            return
        
        total_chips_bought += chips_bought
        total_chips_end += chips_end
        difference = chips_end - chips_bought
        amount = difference * (ratio / 1000)  # חישוב ההמרה לפי יחס - ש"ח

        players_data.append({
            'name': name,
            'amount': amount
        })

        if amount > 0:
            message += f"{name} צריך לקבל {amount} ₪\n"
        elif amount < 0:
            message += f"{name} צריך לשלם {abs(amount)} ₪\n"
    
    # חישוב טווח טעות של 5% מסך הצ'יפים שנקנו
    tolerance = total_chips_bought * 0.05
    chip_difference = abs(total_chips_bought - total_chips_end)
    
    # בדיקה אם כמות הצ'יפים סבירה בהתחשב בטווח הטעות
    if chip_difference > tolerance:
        await update.message.reply_text("שגיאה: כמות הצ'יפים שנקנו שונה מכמות הצ'יפים שנמצאו בסוף בצורה משמעותית.")
        return
    
    # חלוקת הטעות בין כל המשתתפים
    if chip_difference > 0:
        adjustment_per_player = (chip_difference * (ratio / 1000)) / len(players_data)
        for player in players_data:
            player['amount'] -= adjustment_per_player
    
    # חישוב העברות כספיות בין השחקנים
    debtors = [p for p in players_data if p['amount'] < 0]
    creditors = [p for p in players_data if p['amount'] > 0]

    # הודעה לסיכום העברות בין השחקנים
    transfer_message = "\nהעברות כספיות:\n"
    
    while debtors and creditors:
        debtor = debtors.pop()
        creditor = creditors.pop()
        
        amount_to_transfer = min(abs(debtor['amount']), creditor['amount'])
        transfer_message += f"{debtor['name']} צריך להעביר {amount_to_transfer} ₪ ל{creditor['name']}\n"

        debtor['amount'] += amount_to_transfer
        creditor['amount'] -= amount_to_transfer

        if debtor['amount'] < 0:
            debtors.append(debtor)
        if creditor['amount'] > 0:
            creditors.append(creditor)

    # שליחת ההודעות
    await update.message.reply_text(message + transfer_message)
    
async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = 'מחיקת המשחק:\n'

    # חישוב רווחים והפסדים
    for player in players_collection.find():
        
        players_collection.delete_one(player)
        message+= f"שחקן {player['name']} נמחק\n"
    await update.message.reply_text(message)

async def debug(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = 'נתוני המשחק:\n'

    # חישוב רווחים והפסדים
    for player in players_collection.find():
        message+= f"שחקן {player['name']} קנה {player['chips_bought']} צ'יפים וסיים עם {player['chips_end']} צ'יפים\n"
    await update.message.reply_text(message)
    
# הגדרת הפונקציה הראשית להפעלת הבוט
def main():
    application = Application.builder().token(TOKEN).build()

    # הוספת פקודות לבוט
    application.add_handler(CommandHandler("buy", buy))
    application.add_handler(CommandHandler("end", end))
    application.add_handler(CommandHandler("summary", summary))
    application.add_handler(CommandHandler("clear", clear))
    application.add_handler(CommandHandler("debug", debug))

    # התחלת הבוט
    application.run_polling()

if __name__ == '__main__':
    main()
