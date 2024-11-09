import os
from matplotlib.cm import ScalarMappable
from ultralytics import YOLO

import cv2
import numpy as np
from PIL import Image

# נתיב הבסיס: מחושב אוטומטית לפי מיקום bot.py
base_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(base_dir)  # Set the current working directory to base_dir

def preprocess_card_image(image_path):
    # טוען את התמונה המקורית
    image = cv2.imread(image_path)
    
    # שלב 1: הפיכת התמונה לגווני אפור
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # שלב 2: הגברת הניגודיות באמצעות histogram equalization
    enhanced_gray = cv2.equalizeHist(gray)
    
    # שלב 3: החלת סף להדגשת הקלפים, תוך שמירה על פרטים
    _, thresh = cv2.threshold(enhanced_gray, 150, 255, cv2.THRESH_BINARY_INV)
    
    # שלב 4: הוספת מעט מסגרת מסביב לקלף
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    bordered = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
    
    # שלב 5: נקה רעש חיצוני (במיוחד אם יש אזורים בהירים קטנים בתמונה)
    clean_image = cv2.medianBlur(bordered, 5)
    
    return clean_image

# Load a model
# data_path = os.path.join(os.path.expanduser("~"), "Nutrino/datasets/playing-cards-trainning-set/data.yaml")
# model = YOLO("yolov8n.yaml")  # build a new model from scratch
# results = model.train(data=data_path, epochs=3)  # train the model
# results = model.val()  # evaluate model performance on the validation set
# success = YOLO("yolov8n.pt").export(format="onnx")  # export a model to ONNX format

# מעבר על כל קובצי HEIC בתיקייה
#model_1 = YOLO("./yolov8m_synthetic.pt")
model_2 = YOLO("./yolov8s_playing_cards-1.pt")
#model_3 = YOLO("./yolov8s_playing_cards-2.pt")

for filename in os.listdir(os.path.join(base_dir,'test-images')):
    if filename.find("processed") != -1 or filename.find(".jpg") == -1:
        continue
    heic_path = os.path.join(os.path.join(base_dir,'test-images'), filename)
    jpg_path = heic_path.replace(".HEIC", ".jpg")

    if not os.path.exists(jpg_path):
        with Image.open(heic_path) as img:
            img.convert("RGB").save(jpg_path, "JPEG")
       
    # קריאה לתמונה והכנה
    #processed_image = preprocess_card_image(jpg_path)
    #processed_path = jpg_path.replace(".jpg", "_processed.jpg")
    #cv2.imwrite(processed_path, processed_image)

    #results1 = model_1(jpg_path)
    results2 = model_2(jpg_path,)
    #results3 = model_2(processed_path)

    # הדפסת זיהויים עבור קלפים בלבד
    for i, results in enumerate([results2], 1):
        identified = set()
        for result in results:
            if result.boxes:
                for box in result.boxes:
                    card_label = result.names[int(box.cls)]
                    identified.add(card_label)
        print(f"{filename}: {identified}")
