# שלב בסיסי עם Python
FROM python:3.10

# התקנת Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# הוספת Poetry ל- PATH
ENV PATH="/root/.local/bin:$PATH"

# Install required packages including libgl1
RUN apt-get update && \
    apt-get install -y libgl1-mesa-glx && \
    apt-get clean
    
# הפעלת Poetry ללא סביבה וירטואלית
ENV POETRY_VIRTUALENVS_CREATE=false

# הגדרת ספריית עבודה
WORKDIR /app

# העברת קבצי הפרויקט (כולל pyproject.toml ו-poetry.lock)
COPY pyproject.toml poetry.lock ./

RUN poetry install --no-root --verbose
RUN poetry show

COPY . .

# פקודת הרצה ראשית.
CMD [ "python", "bot.py"]
