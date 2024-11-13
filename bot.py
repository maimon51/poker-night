import os
from datetime import datetime
from pymongo import MongoClient
from telegram import Update, error
from telegram.ext import Application, CommandHandler, CallbackContext, ContextTypes, MessageHandler, filters
import json
from treys import Card, Deck, Evaluator
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import tempfile
#from matplotlib.cm import ScalarMappable
from ultralytics import YOLO

#import cv2
#import numpy as np
#from PIL import Image

# נתיב הבסיס: מחושב אוטומטית לפי מיקום bot.py
base_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(base_dir)  # Set the current working directory to base_dir

# def preprocess_card_image(image_path):
#     # טוען את התמונה המקורית
#     image = cv2.imread(image_path)
    
#     # שלב 1: הפיכת התמונה לגווני אפור
#     gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
#     # שלב 2: הגברת הניגודיות באמצעות histogram equalization
#     enhanced_gray = cv2.equalizeHist(gray)
    
#     # שלב 3: החלת סף להדגשת הקלפים, תוך שמירה על פרטים
#     _, thresh = cv2.threshold(enhanced_gray, 150, 255, cv2.THRESH_BINARY_INV)
    
#     # שלב 4: הוספת מעט מסגרת מסביב לקלף
#     kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
#     bordered = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
    
#     # שלב 5: נקה רעש חיצוני (במיוחד אם יש אזורים בהירים קטנים בתמונה)
#     clean_image = cv2.medianBlur(bordered, 5)
    
#     return clean_image

# Load a model
# data_path = os.path.join(os.path.expanduser("~"), "Nutrino/datasets/playing-cards-trainning-set/data.yaml")
# model = YOLO("yolov8n.yaml")  # build a new model from scratch
# results = model.train(data=data_path, epochs=3)  # train the model
# results = model.val()  # evaluate model performance on the validation set
# success = YOLO("yolov8n.pt").export(format="onnx")  # export a model to ONNX format

# מעבר על כל קובצי HEIC בתיקייה
#model_1 = YOLO("./yolov8m_synthetic.pt")
#model_2 = YOLO("./yolov8s_playing_cards-1.pt")
#model_3 = YOLO("./yolov8s_playing_cards-2.pt")

# for filename in os.listdir(os.path.join(base_dir,'test-images')):
#     if filename.find("processed") != -1 or filename.find(".jpg") == -1:
#         continue
#     heic_path = os.path.join(os.path.join(base_dir,'test-images'), filename)
#     jpg_path = heic_path.replace(".HEIC", ".jpg")

#     if not os.path.exists(jpg_path):
#         with Image.open(heic_path) as img:
#             img.convert("RGB").save(jpg_path, "JPEG")
       
#     # קריאה לתמונה והכנה
#     #processed_image = preprocess_card_image(jpg_path)
#     #processed_path = jpg_path.replace(".jpg", "_processed.jpg")
#     #cv2.imwrite(processed_path, processed_image)

#     #results1 = model_1(jpg_path)
#     results2 = model_2(jpg_path)
#     #results3 = model_2(processed_path)

#     # הדפסת זיהויים עבור קלפים בלבד
#     for i, results in enumerate([results2], 1):
#             print(f"\nModel {i} detections:")
#             for result in results:
#                 if result.boxes:
#                     for box in result.boxes:
#                         card_label = result.names[int(box.cls)]
#                         print(f"Identified card: {card_label}")
#                 else:
#                     print("No cards identified.")

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
# Card identification logic
# ==========================
def get_distinct_identified_cards(model, image_path):
    results = model(image_path)
    
    card_confidences = []
    for result in results:
        if result.boxes:
            for box in result.boxes:
                card_label = result.names[int(box.cls)]
                confidence = box.conf  # Confidence score for the detection
                print (f"Identified card: {card_label} with confidence: {confidence}")
                card_confidences.append((card_label, confidence))
                
        # Sort by confidence score in descending order 
        top_cards = sorted(card_confidences, key=lambda x: x[1], reverse=True)
        # Format output as a set of top two distinct cards
        distinct_top_cards = {card for card, conf in top_cards if conf > 0.45}
        
    return list(distinct_top_cards)  # Convert to list if needed

model_2 = YOLO("./yolov8s_playing_cards-1.pt")
# for filename in os.listdir(os.path.join(base_dir,'test-images')):
#     if filename.find("HEIC") != -1:
#         heic_path = os.path.join(os.path.join(base_dir,'test-images'), filename)
#         jpg_path = heic_path.replace(".HEIC", ".jpg")

#         if not os.path.exists(jpg_path):
#             with Image.open(heic_path) as img:
#                 img.convert("RGB").save(jpg_path, "JPEG")
#         continue
                
#     if filename.find("processed") != -1 or filename.find(".jpg") == -1:
#         continue
#     cards = get_distinct_identified_cards(model_2, os.path.join(os.path.join(base_dir,'test-images'), filename))
#     print(f"Identified cards in {filename}: {cards}")

# ==========================
# Web server for summary
# ==========================
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

# ========================================
# Data access and general utlity functions
# ========================================
def parse_card_input(card_str):
    """ממירה את הקלט של הקלף לפורמט מתאים """
    
    # המרה לאותיות גדולות וניקוי רווחים
    card_str = card_str.strip().upper()

    # המרה של "10" ל-"T" כדי להתאים לפורמט של STR_RANKS
    card_str = card_str.replace("10", "T")

    # בדיקת תקינות פורמט הקלט
    if len(card_str) != 2:
        raise ValueError(f"קלט לא תקין עבור הקלף: {card_str}")
    
    # פיצול לרמה וסוג
    rank, suit = card_str[0], card_str[1].lower()  # סוג הקלף באות קטנה כדי להתאים למיפוי

    # המרה לפורמט מתאים
    return Card.new(f"{rank}{suit}")

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
            "status": "active",
            "total_chips_end": 0  # שדה חדש עבור סך הצ'יפים הסופיים
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
    return players_collection.find_one({"chat_id": chat_id, "game_id": game_id, "name": name.lower()})

async def send_message(update, message):
    """ שולחת הודעה לצ'אט הנוכחי """
    await update.message.reply_text(message)  

async def display_summary(update: Update, ratio: float):
    """מחשב ומציג סיכום המשחק בהתאם ליחס ההמרה שניתן"""
    chat_id = update.effective_chat.id
    game_id = get_or_create_active_game(chat_id)

    message = f'סיכום המשחק:\nיחס המרה ₪{ratio}/1000\n'
    players_data = []

    # חישוב רווחים והפסדים עבור כל שחקן
    for player in players_collection.find({"chat_id": chat_id, "game_id": game_id}):
        name = player['name']
        chips_bought, chips_end = player.get('chips_bought'), player.get('chips_end')
        
        if chips_bought is None or chips_end is None:
            await send_message(update, f"שחקן {name} עדיין לא השלים את הנתונים")
            return
        
        difference = chips_end - chips_bought
        amount = difference * (ratio / 1000)
        players_data.append({'name': name, 'amount': amount})

        message += f"{name} צריך {'לקבל' if amount > 0 else 'לשלם'} {abs(amount):.2f} ₪\n"
    
    # שמירת דירוג המשחק במסד הנתונים
    sorted_players_data = sorted(players_data, key=lambda x: x['amount'], reverse=True)
    games_collection.update_one(
        {"_id": game_id},
        {"$set": {"ranking": sorted_players_data}}
    )
    
    # חישוב העברות כספיות
    transfer_message = "\nהעברות כספיות:\n"
    debtors = [p for p in players_data if p['amount'] < 0]
    creditors = [p for p in players_data if p['amount'] > 0]
    
    while debtors and creditors:
        debtor = debtors.pop()
        creditor = creditors.pop()
        transfer_amount = min(abs(debtor['amount']), creditor['amount'])
        
        # הודעה על העברה
        transfer_message += f"{debtor['name']} צריך להעביר {transfer_amount:.2f} ₪ ל{creditor['name']}\n"
        
        # עדכון הסכומים
        debtor['amount'] += transfer_amount
        creditor['amount'] -= transfer_amount

        # החזרת השחקנים לרשימות אם עדיין יש להם חוב/זכות
        if debtor['amount'] < 0:
            debtors.append(debtor)
        if creditor['amount'] > 0:
            creditors.append(creditor)

    # שליחת הודעת הסיכום עם העברות כספיות
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

def get_total_bought(game_id):
    """מחזירה את סך הצ'יפים שנקנו במשחק."""
    total_bought_cursor = players_collection.aggregate([
        {"$match": {"game_id": game_id}},
        {"$group": {"_id": None, "total_bought": {"$sum": "$chips_bought"}}}
    ])
    total_bought_result = list(total_bought_cursor)
    return total_bought_result[0]["total_bought"] if total_bought_result else 0

def get_unfinished_players(game_id):
    """מחזירה את רשימת השחקנים שלא סיימו את המשחק (ללא ערך צ'יפים סופי)."""
    return list(players_collection.find({"game_id": game_id, "chips_end": None}))

def update_total_chips_end(game_id):
    """מחשב מחדש ומעדכן את סך הצ'יפים הסופיים במשחק."""
    total_end_cursor = players_collection.aggregate([
        {"$match": {"game_id": game_id, "chips_end": {"$ne": None}}},
        {"$group": {"_id": None, "total_end": {"$sum": "$chips_end"}}}
    ])
    total_end_result = list(total_end_cursor)
    total_end = total_end_result[0]["total_end"] if total_end_result else 0

    # עדכון הערך המחושב במסד הנתונים
    games_collection.update_one(
        {"_id": game_id},
        {"$set": {"total_chips_end": total_end}}
    )

# ==========================
# probability calculations
# ==========================

# מטמון בזיכרון
win_probability_cache = {}
def create_probability_message(hole_cards, community_cards, hand_stats, multi_win_probability, single_win_probability):
    """Generate a formatted message with game statistics and probabilities."""
    
    # הצגת קלפי השחקן וקלפי הקהילה בפורמט פשוט
    hole_cards_display = f"{Card.int_to_pretty_str(hole_cards[0])} {Card.int_to_pretty_str(hole_cards[1])}"
    community_cards_display = ' '.join([Card.int_to_pretty_str(card) for card in community_cards])

    # עיצוב הפלט להודעה
    message = (
        f"קלפי השחקן: {hole_cards_display}\n"
        f"קלפי הקהילה: {community_cards_display}\n"
    )
    
    # טבלת סיכויי ידיים עבור כל היריבים
    message += f"\n{'Hand':<15} | {'Player':<10}\n"
    message += "════════════════\n"
    for hand_type, (player_percent, _, _) in sorted(hand_stats.items(), key=lambda x: x[1][0], reverse=True):
        if player_percent > 0:
            player_display = f"{player_percent:>6.2f}%"
            message += f"{hand_type:<15} | {player_display}\n"
            
    if multi_win_probability is not None:
        # סיכוי לניצחון, תיקו והפסד עבור כלל היריבים
        message += f"מול כולם - ✅ סיכוי לניצחון: {multi_win_probability:.2f}%\n"

    # סיכוי לניצחון, תיקו והפסד עבור יריב אחד בלבד
    message += f"ראש בראש - ✅ סיכוי לניצחון: {single_win_probability:.2f}%\n\n"

    return message

async def calculate_detailed_probability(update, hole_cards, community_cards):
    """Calculate win probability with detailed breakdown based on hand types."""
    game_id = get_or_create_active_game(update.effective_chat.id)

    evaluator = Evaluator()
    opponent_count = players_collection.count_documents(
        {"chat_id": update.effective_chat.id, "game_id": game_id}
    ) - 1

    if opponent_count < 1:
        await send_message(update, "יש לפחות יריב אחד לחישוב הסיכויים.")
        return

    num_simulations = 2000
    hand_counts = {
        "Royal Flush": 0,
        "Straight Flush": 0,
        "Four of a Kind": 0,
        "Full House": 0,
        "Flush": 0,
        "Straight": 0,
        "Three of a Kind": 0,
        "Two Pair": 0,
        "Pair": 0,
        "High Card": 0
    }
    
    # בדיקה אם יש יותר מיריב אחד
    if opponent_count > 1:
        opponent_hand_counts = hand_counts.copy()
        multi_player_wins = 0

    single_opponent_hand_counts = hand_counts.copy()
    single_opponent_wins = 0

    for _ in range(num_simulations):
        try:
            # הגדרת חבילת קלפים עבור סימולציה מול כל היריבים
            deck = Deck()
            deck.cards = [card for card in deck.cards if card not in hole_cards + community_cards]

            # שליפת קלפים לקהילה
            community_draw = deck.draw(5 - len(community_cards))
            full_community_cards = community_cards + community_draw

            # חישוב יד השחקן
            player_score = evaluator.evaluate(hole_cards, full_community_cards)
            player_hand_type = evaluator.get_rank_class(player_score)
            hand_counts[evaluator.class_to_string(player_hand_type)] += 1
            
            # חישוב מול כל היריבים אם יש יותר מיריב אחד
            if opponent_count > 1:
                opponent_hands = [deck.draw(2) for _ in range(opponent_count)]
                opponent_best_score = min(evaluator.evaluate(hand, full_community_cards) for hand in opponent_hands)
                opponent_best_hand_type = evaluator.get_rank_class(opponent_best_score)
                opponent_hand_counts[evaluator.class_to_string(opponent_best_hand_type)] += 1

                if player_score < opponent_best_score:
                    multi_player_wins += 1

            # סימולציה נפרדת מול יריב אחד בלבד
            single_opponent_deck = Deck()
            single_opponent_deck.cards = [card for card in single_opponent_deck.cards if card not in hole_cards + community_cards]
            single_opponent_hand = single_opponent_deck.draw(2)
            single_opponent_score = evaluator.evaluate(single_opponent_hand, full_community_cards)
            single_opponent_hand_type = evaluator.get_rank_class(single_opponent_score)
            single_opponent_hand_counts[evaluator.class_to_string(single_opponent_hand_type)] += 1

            if player_score < single_opponent_score:
                single_opponent_wins += 1
        except Exception as e:
            print(f"Error in simulation iteration: {e}")

    # חישוב אחוזים לכל יד
    hand_stats = {}
    for hand_type in hand_counts:
        player_percent = (hand_counts[hand_type] / num_simulations) * 100
        opponent_percent = (opponent_hand_counts[hand_type] / num_simulations) * 100 if opponent_count > 1 else 0
        single_opponent_percent = (single_opponent_hand_counts[hand_type] / num_simulations) * 100

        # סינון תוצאות קרובות ל-0% בשלב ההדפסה
        if player_percent > 0.01 or opponent_percent > 0.01 or single_opponent_percent > 0.01:
            hand_stats[hand_type] = (player_percent, opponent_percent, single_opponent_percent)

    # אחוזי ניצחון ותיקו עבור כל היריבים ועבור יריב אחד
    multi_win_probability = (multi_player_wins / num_simulations) * 100 if opponent_count > 1 else None
    single_win_probability = (single_opponent_wins / num_simulations) * 100

    # יצירת הודעת טקסט עם הסיכויים
    message = create_probability_message(
        hole_cards, community_cards, hand_stats,
        multi_win_probability, single_win_probability)
    
    # generate feedback for the player based on the current hand and probabilities
    previous_win_probability = get_previous_win_probability_cache(game_id) or None
    if not community_cards:
        player_hand_type = "Pair" if Card.get_rank_int(hole_cards[0]) == Card.get_rank_int(hole_cards[1]) else "High Card"
    else:
        player_score = evaluator.evaluate(hole_cards, community_cards)
        player_hand_type = evaluator.class_to_string(evaluator.get_rank_class(player_score))
    feedback = generate_feedback(player_hand_type, hand_stats, multi_win_probability, previous_win_probability)
    update_previous_win_probability_cache(game_id, multi_win_probability)

    await send_message(update, message + feedback)

def generate_hand_feedback(current_hand):
    """Generates detailed strategic suggestions based on the current hand."""
    feedback_message = f"\n🔍 היד הנוכחית שלך: {current_hand}\n"
    
    feedback_message += "\n📝 המלצה:\n"
    if current_hand == "Four of a Kind":
        feedback_message += (
            "🎉 יש לך ארבעה קלפים זהים! זהו אחד המקרים החזקים ביותר. זה הזמן להעלות את ההימור "
            "ולנסות למקסם את הרווח מהיריבים שלך.\n"
        )
    elif current_hand == "Full House":
        feedback_message += (
            "🏠 יש לך פול האוס - יד חזקה מאוד! תוכל לשקול להעלות את ההימור, אך עקוב אחרי התגובות של היריבים, "
            "כדי להימנע מהפסד מיותר במקרה של יריב עם יד גבוהה יותר.\n"
        )
    elif current_hand == "Flush":
        feedback_message += (
            "♠ יש לך צבע! זו יד חזקה. נסה להעלות את ההימור כדי להפעיל לחץ על יריבים "
            "פחות בטוחים. אך שים לב לקלפי הקהילה, ייתכן שיש ליריב רצף חזק.\n"
        )
    elif current_hand == "Straight":
        feedback_message += (
            "🔗 יש לך רצף! זהו מצב טוב, אך לא החזק ביותר. כדאי לשקול העלאה קטנה או לשחק בזהירות, במיוחד אם "
            "יש לך רצף נמוך וקלפים גבוהים בשולחן.\n"
        )
    elif current_hand == "Three of a Kind":
        feedback_message += (
            "👀 יש לך שלשה. יד סבירה אך אינה החזקה ביותר. עדיף להיזהר אם היריבים מעלים את ההימור, "
            "כי ייתכן שמישהו מחזיק יד חזקה יותר.\n"
        )
    elif current_hand == "Two Pair":
        feedback_message += (
            "✌️ יש לך זוגיים. יד טובה יחסית, אך כדאי לשחק בזהירות ולבדוק את התגובות של היריבים. "
            "אם ישנו הימור גבוה, ייתכן שכדאי לפרוש.\n"
        )
    elif current_hand == "Pair":
        feedback_message += (
            "🃏 יש לך זוג. יד בסיסית, אך כדאי לשקול את ההימור בזהירות רבה. אם היריבים מעלים משמעותית, "
            "עדיף לסגת ולשמור על הצ'יפים.\n"
        )
    else:
        feedback_message += (
            "💧 אין לך יד חזקה. עדיף לשקול לפרוש ולהמתין להזדמנות טובה יותר. הישאר במשחק רק אם ההימור נמוך."
        )
    
    return feedback_message
    
def generate_feedback(current_hand, hand_stats, win_probability, previous_win_probability=None, stage=None):
    """
    יוצר פידבק לשחקן עם עצות מפורטות בהתאם לידו הנוכחית ולשלבי המשחק.
    
    Parameters:
    - current_hand: str, סוג היד הנוכחית של השחקן (למשל: "Pair", "Flush")
    - hand_stats: dict, סיכויי הידיים של היריבים לפי סוגי ידיים
    - win_probability: float, סיכוי הניצחון הנוכחי של השחקן באחוזים
    - previous_win_probability: float, סיכוי הניצחון מהשלב הקודם, אם קיים
    
    Returns:
    - str, הודעת טקסט עם פידבק אסטרטגי לשחקן
    """
    
    feedback_message = ""
    
    # השוואה לשלב הקודם אם קיים
    if previous_win_probability is not None:
        delta = abs(win_probability - previous_win_probability)
        
        if delta <= 2:  # שינוי זניח של עד 2%
            feedback_message += "➡ מצבך נותר כמעט ללא שינוי מהשלב הקודם.\n"
        elif win_probability > previous_win_probability:
            feedback_message += "⬆ היד שלך התחזקה ביחס לשלב הקודם.\n"
        else:
            feedback_message += "⬇ היד שלך נחלשה. שקול את המשך הפעולות שלך בזהירות.\n"

    feedback_message += generate_hand_feedback(current_hand)
    
    # מיון והצגת רק הידיים המסוכנות ביותר עם סיכוי גבוה (רק זוגיים ומעלה)
    risk_hands = [
        f'{hand} {chance:.2f}%'
        for hand, (_, chance, _) in sorted(hand_stats.items(), key=lambda x: x[1][1], reverse=True)
        if chance > 10 and hand in {"Two Pair", "Three of a Kind", "Straight", "Flush", "Full House", "Four of a Kind", "Straight Flush", "Royal Flush"}
    ]

    if risk_hands:
        feedback_message += "\n⚠ שים לב! ליריבים יש סיכוי גבוה להשיג ידיים חזקות כמו:\n"
        feedback_message += "\n".join(risk_hands)
        feedback_message += "\n. התכונן להתמודד עם ידיים חזקות ולהימנע מהפתעות.\n"
        
    return feedback_message

def get_previous_win_probability_cache(game_id):
    """מחזירה את הסיכוי הקודם מהמטמון עבור game_id מסוים, או None אם לא קיים."""
    return win_probability_cache.get(game_id)

def update_previous_win_probability_cache(game_id, new_probability):
    """מעדכנת את הסיכוי הקודם במטמון עבור game_id מסוים."""
    win_probability_cache[game_id] = new_probability
    
# ==========================
# BOT handlers for commands
# ==========================
async def hole(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Receive player's hole cards and start game tracking with initial probability calculation."""
    if len(context.args) != 2:
        await update.message.reply_text("שימוש: /hole <Card1> <Card2> (למשל /hole Qh Qs)")
        return

    try:
        card1 = parse_card_input(context.args[0])
        card2 = parse_card_input(context.args[1])
        game_id = get_or_create_active_game(update.effective_chat.id)

        # שמירת קלפי השחקן בבסיס הנתונים
        games_collection.update_one(
            {"_id": game_id},
            {"$set": {"hole_cards": [card1, card2], "flop": [], "turn": None, "river": None}}
        )

        # חישוב הסיכויים הראשוניים עם 5 קלפי קהילה אקראיים
        await calculate_detailed_probability(update, [card1, card2], [])

    except Exception as e:
        await update.message.reply_text(f"שגיאה: {e}")

async def flop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Receive flop cards and update them in the database."""
    if len(context.args) != 3:
        await update.message.reply_text("שימוש: /flop <Card1> <Card2> <Card3> (למשל /flop 7h 8d 9c)")
        return

    try:
        game_id = get_or_create_active_game(update.effective_chat.id)
        hole_cards = games_collection.find_one({"_id": game_id}).get("hole_cards")

        if not hole_cards:
            await update.message.reply_text("לא הגדרת עדיין את הקלפים שלך. השתמש ב-/hole.")
            return

        flop_cards = [parse_card_input(card) for card in context.args]

        # שמירת קלפי הפלופ בלבד
        games_collection.update_one(
            {"_id": game_id},
            {"$set": {"flop": flop_cards}}
        )

        await calculate_detailed_probability(update, hole_cards, flop_cards)

    except Exception as e:
        await update.message.reply_text(f"שגיאה: {e}")

async def turn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Receive turn card and update it in the database."""
    if len(context.args) != 1:
        await update.message.reply_text("שימוש: /turn <Card> (למשל /turn Jh)")
        return

    try:
        game_id = get_or_create_active_game(update.effective_chat.id)
        game_data = games_collection.find_one({"_id": game_id})
        hole_cards = game_data.get("hole_cards")
        flop_cards = game_data.get("flop", [])

        if not hole_cards or len(flop_cards) < 3:
            await update.message.reply_text("חסר מידע. השתמש ב-/hole ו-/flop לפני השימוש ב-/turn.")
            return

        turn_card = parse_card_input(context.args[0])

        # שמירת קלף הטרן בלבד
        games_collection.update_one(
            {"_id": game_id},
            {"$set": {"turn": turn_card}}
        )

        await calculate_detailed_probability(update, hole_cards, flop_cards + [turn_card])

    except Exception as e:
        await update.message.reply_text(f"שגיאה: {e}")

async def river(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Receive river card and update it in the database."""
    if len(context.args) != 1:
        await update.message.reply_text("שימוש: /river <Card> (למשל /river Qc)")
        return

    try:
        game_id = get_or_create_active_game(update.effective_chat.id)
        game_data = games_collection.find_one({"_id": game_id})
        hole_cards = game_data.get("hole_cards")
        flop_cards = game_data.get("flop", [])
        turn_card = game_data.get("turn")

        if not hole_cards or len(flop_cards) < 3 or not turn_card:
            await update.message.reply_text("חסר מידע. השתמש ב-/hole, /flop ו-/turn לפני השימוש ב-/river.")
            return

        river_card = parse_card_input(context.args[0])

        # שמירת קלף הריבר בלבד
        games_collection.update_one(
            {"_id": game_id},
            {"$set": {"river": river_card}}
        )

        await calculate_detailed_probability(update, hole_cards, flop_cards + [turn_card, river_card])

    except Exception as e:
        await update.message.reply_text(f"שגיאה: {e}")
 
# =================================
# BOT utility and summary commands
# =================================
async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    game_id = get_or_create_active_game(chat_id)

    message = 'מחיקת המשחק:\n'

    # מחיקת שחקנים בצ'אט הנוכחי בלבד
    result = players_collection.delete_many({"chat_id": chat_id, "game_id": game_id})
    games_collection.update_one(
        {"_id": game_id},
        {"$set": {"ranking": []}}
    )
    games_collection.update_one(
            {"_id": game_id},
            {"$set": {"hole_cards": [], "flop": [], "turn": None, "river": None}}
    )
    
    message += f"{result.deleted_count} שחקנים קלפים ודרוג נמחקו\n"
    await update.message.reply_text(message)

async def debug(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    game_id = get_or_create_active_game(chat_id)
    message = 'נתוני המשחק:\n'

    # הצגת נתוני שחקנים בצ'אט הנוכחי בלבד
    for player in players_collection.find({"chat_id": chat_id, "game_id": game_id}):
        message += f"שחקן {player['name']} קנה {player['chips_bought']} צ'יפים וסיים עם {player['chips_end']} צ'יפים\n"
    
    # הוספת מידע על מצב המשחק הנוכחי
    game_data = games_collection.find_one({"_id": game_id})
    if game_data:
        # קלפי השחקן
        hole_cards = game_data.get("hole_cards", [])
        if hole_cards:
            hole_cards_str = " ".join([Card.int_to_pretty_str(card) for card in hole_cards])
            message += f"\nקלפי השחקן: {hole_cards_str}\n"
        else:
            message += "\nקלפי השחקן לא הוגדרו עדיין.\n"

        # קלפי הפלופ
        flop_cards = game_data.get("flop", [])
        if flop_cards:
            flop_cards_str = " ".join([Card.int_to_pretty_str(card) for card in flop_cards])
            message += f"קלפי הפלופ: {flop_cards_str}\n"
        else:
            message += "קלפי הפלופ לא הוגדרו עדיין.\n"

        # קלף הטרן
        turn_card = game_data.get("turn")
        if turn_card:
            turn_card_str = Card.int_to_pretty_str(turn_card)
            message += f"קלף הטרן: {turn_card_str}\n"
        else:
            message += "קלף הטרן לא הוגדר עדיין.\n"

        # קלף הריבר
        river_card = game_data.get("river")
        if river_card:
            river_card_str = Card.int_to_pretty_str(river_card)
            message += f"קלף הריבר: {river_card_str}\n"
        else:
            message += "קלף הריבר לא הוגדר עדיין.\n"

        # שלב המשחק (לפי הקלפים שהוגדרו עד כה)
        if river_card:
            stage = "ריבר"
        elif turn_card:
            stage = "טרן"
        elif flop_cards:
            stage = "פלופ"
        else:
            stage = "התחלה"
        
        message += f"שלב המשחק: {stage}\n"
    else:
        message += "אין מידע על המשחק הנוכחי.\n"

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
       
async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    games = games_collection.find({"chat_id": chat_id}).sort("start_date", -1)
    message = "היסטוריית משחקים:\n"
    count = 1
    for game in games:
        start_date = game["start_date"].strftime("%Y-%m-%d %H:%M") if game["start_date"] else "לא ידוע"
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
 
# ==========================
# Bot handler utilities
# ==========================
async def handle_buy(update: Update, message_text: str) -> None:
    """פונקציה לטיפול בקניית צ'יפים עם פורמט '+<כמות> <שמות>'"""
    chat_id = update.effective_chat.id
    game_id = get_or_create_active_game(chat_id)
    initialize_game_start_date_if_needed(game_id)

    try:
        # מסירים את התו `+` ומחלקים
        parts = message_text[1:].split()
        chips_bought = int(parts[0])
        names = parts[1:]

        if not names:
            await send_message(update, "שימוש: +<כמות צ'יפים> <שם1> <שם2> ...")
            return

        messages = []
        for name in names:
            player = get_player_data(chat_id, game_id, name)
            if player:
                chips_total = chips_bought + player['chips_bought']
                players_collection.update_one(
                    {"_id": player["_id"]},
                    {"$set": {"chips_bought": chips_total}}
                )
                messages.append(f"שחקן {name} קיים, נוספו לו {chips_bought} צ'יפים (סה\"כ {chips_total})")
            else:
                players_collection.insert_one({
                    "chat_id": chat_id,
                    "game_id": game_id,
                    "name": name.lower(),
                    "chips_bought": chips_bought,
                    "chips_end": None
                })
                messages.append(f"שחקן {name} נוסף עם {chips_bought} צ'יפים")

        await send_message(update, "\n".join(messages))
    except (IndexError, ValueError):
        await send_message(update, "שימוש: +<כמות צ'יפים> <שם1> <שם2> ...")

async def handle_end(update: Update, message_text: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process end command in the format '<name>=<amount>'."""
    chat_id = update.effective_chat.id
    game_id = get_or_create_active_game(chat_id)

    try:
        # Parse message text for end command format
        name, chips_end = message_text.split('=')
        name, chips_end = name.strip(), int(chips_end.strip())
        
        player = get_player_data(chat_id, game_id, name)

        if player:
            players_collection.update_one({"_id": player["_id"]}, {"$set": {"chips_end": chips_end}})
            update_total_chips_end(game_id)            
            await send_message(update, f"שחקן {name} סיים עם {chips_end} צ'יפים")
        else:
            await send_message(update, f"שחקן {name} לא קיים")
            return
        
        # בדיקה אם נשאר רק שחקן אחד ללא ערך צ'יפים סופי
        unfinished_players = get_unfinished_players(game_id)
        if len(unfinished_players) == 1:
            remaining_player = unfinished_players[0]

            # חישוב הצ'יפים הנותרים עבור השחקן האחרון
            total_bought = get_total_bought(game_id)
            total_end = games_collection.find_one({"_id": game_id}).get("total_chips_end", 0)
            remaining_chips = total_bought - total_end

            # עדכון השחקן האחרון עם סכום הצ'יפים הנותרים
            players_collection.update_one(
                {"_id": remaining_player["_id"]},
                {"$set": {"chips_end": remaining_chips}}
            )
            await send_message(update, f"שחקן {remaining_player['name']} הושלם אוטומטית עם {remaining_chips} צ'יפים.")
            
            # כל השחקנים סיימו והסכום תואם - בקשה ליחס המרה
            await send_message(update, "כל השחקנים סיימו את המשחק. אנא הזן את יחס ההמרה (מחיר קניית אלף ציפים):")
            
            # הפעלת מצב המתנה ליחס המרה
            context.user_data["awaiting_ratio"] = True
                       
    except (IndexError, ValueError):
        await send_message(update, "שימוש: <שם>=<כמות צ'יפים סופית>")

# ==========================
# Message Handler Main
# ==========================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Main handler for regular messages and images."""
    # בדיקה אם ההודעה מכילה תמונה
    if update.message.photo:
        # קבלת מזהה המשחק הפעיל
        game_id = get_or_create_active_game(update.effective_chat.id)
        game_data = games_collection.find_one({"_id": game_id})
        
        # הורדת התמונה
        photo_file = await update.message.photo[-1].get_file()
        tempfilename = f"{tempfile.gettempdir()}/{photo_file.file_id}.jpg"
        await photo_file.download_to_drive(tempfilename)

        # זיהוי הקלפים בתמונה
        detected_cards = get_distinct_identified_cards(model_2, tempfilename)
        await send_message(update,f"קלפים שזוהו: {detected_cards}")

        try:
            # טיפול בהתאם לכמות הקלפים שנמצאו
            if len(detected_cards) == 2:
                # קלפי "חור" - שליחת פקודת hole
                context.args = detected_cards
                await hole(update, context)
            elif len(detected_cards) == 3:
                # קלפי "פלופ" - שליחת פקודת flop
                context.args = detected_cards
                await flop(update, context)
            elif len(detected_cards) == 4:
                # get flop cards to identify the forth card
                flop_cards = game_data.get("flop", [])
                turn_card = [card for card in detected_cards if card not in flop_cards]
                context.args = [turn_card] 
                await turn(update, context)
            elif len(detected_cards) == 5 :
                # get flop cards and turn to identify the forth card
                flop_cards = game_data.get("flop", [])
                turn_card = game_data.get("turn")
                river_card = [card for card in detected_cards if card not in flop_cards and card != turn_card]
                context.args = [river_card]
                await river(update, context)
            else:
                await send_message(update,"Error: Incorrect number of cards detected for this stage.\n",detected_cards)
                return
        except Exception as e:
            await send_message(update,f"שגיאה: {e}")

        return
    
    
    message_text = update.message.text.strip()

    # בדיקה אם מצפים ליחס המרה
    if context.user_data.get("awaiting_ratio"):
        try:
            # ניסיון להמיר את הטקסט למספר ליחס ההמרה
            ratio = float(message_text)
            await display_summary(update, ratio)
            await endgame(update, context)
        except ValueError:
            await send_message(update, "אנא הזן מספר תקין עבור יחס ההמרה.")
        finally:
            # ניקוי מצב ההמתנה ליחס המרה כדי להחזיר את השליטה להנדלר הרגיל
            context.user_data.pop("awaiting_ratio", None)
        return

    # תהליך רגיל של זיהוי פקודות
    if message_text.startswith("+"):  # זיהוי פקודת קנייה בפורמט `+<כמות> <שמות>`
        await handle_buy(update, message_text)
    elif "=" in message_text:  # זיהוי פקודת סיום בפורמט `<שם>=<כמות>`
        await handle_end(update, message_text, context)
    else:
        await update.message.reply_text("ההודעה לא הובנה. השתמש ב-+ להוספת צ'יפים או בשם=כמות לציון כמות סופית.")

# הוספת הגדרות ל-main
def main():
    # Run the dummy server in a separate thread
    print("Starting dummy server thread")
    threading.Thread(target=start_summary_server, daemon=True).start()
    
    application = Application.builder().token(TOKEN).build()
    handlers = [
        CommandHandler("clear", clear),
        CommandHandler("debug", debug),
        CommandHandler("history", history),
        CommandHandler("stats", stats),
        CommandHandler("hole", hole),
        CommandHandler("flop", flop),
        CommandHandler("turn", turn),
        CommandHandler("river", river),
        MessageHandler(filters.PHOTO | filters.TEXT, handle_message)
    ]
    
    for handler in handlers:
        application.add_handler(handler)
    
    # Define error handler
    async def error_handler(update: Update, context: CallbackContext)-> None:
        print(f"An error occurred: {context.error}")
    
    # Add the error handler to the application
    application.add_error_handler(error_handler)
    
    print("Bot polling")
    application.run_polling(poll_interval=2.0, timeout=10)
    
if __name__ == '__main__':
    main()
