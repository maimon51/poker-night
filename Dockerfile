# Use the slim variant of Python to reduce base image size
FROM python:3.10

# Install dependencies for Poetry and any required libraries
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl libgl1-mesa-glx && \
    curl -sSL https://install.python-poetry.org | python3 - && \
    apt-get purge -y --auto-remove curl && \
    rm -rf /var/lib/apt/lists/*

# Disable creation of a virtual environment
ENV POETRY_VIRTUALENVS_CREATE=false 

# Set the working directory
WORKDIR /app

# Copy only essential files for dependency installation
COPY pyproject.toml poetry.lock ./

# Install dependencies using Poetry
RUN /root/.local/bin/poetry install --no-root --no-dev && \
    # Remove unnecessary cache to reduce image size
    rm -rf ~/.cache/pip

# Copy the rest of the application code
COPY . .

# Run the bot
CMD ["python", "bot.py"]
