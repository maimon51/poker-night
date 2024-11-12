# שלב בסיסי עם Python
FROM python:3.10

# Install required packages including libgl1
RUN curl -sSL https://install.python-poetry.org | python3 - && \
    apt-get update && \
    apt-get install -y libgl1-mesa-glx && \
    apt-get clean
    
ENV PATH="/root/.local/bin:$PATH"
ENV POETRY_VIRTUALENVS_CREATE=false 
    
# הגדרת ספריית עבודה
WORKDIR /app

# העברת קבצי הפרויקט (כולל pyproject.toml ו-poetry.lock)
COPY pyproject.toml poetry.lock ./

RUN poetry install --no-root

COPY . .

CMD [ "python", "bot.py"]
