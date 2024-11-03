# שלב בסיסי עם Python
FROM python:3.9

# התקנת Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# הוספת Poetry ל- PATH
ENV PATH="/root/.local/bin:$PATH"

# הגדרת ספריית עבודה
WORKDIR /app

# העברת קבצי הפרויקט (כולל pyproject.toml ו-poetry.lock)
COPY pyproject.toml poetry.lock ./

RUN poetry install --verbose

COPY . .

# פקודת הרצה ראשית
CMD ["poetry", "run", "python", "bot.py"]
