FROM python:3.12-slim

WORKDIR /app

# System deps needed by psycopg2-binary / PyMuPDF at runtime on slim images
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Run migrations, then start the server. If alembic fails (e.g. DB not
# actually ready despite the healthcheck), the container exits loudly
# instead of serving against a schema-less database.
CMD ["sh", "-c", "alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port 8000"]
