# Backup option: run Casa 24 Wordle anywhere that runs Docker.
# (Vercel does NOT use this file; it uses pyproject.toml.)
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY webapp ./webapp
CMD ["gunicorn", "--chdir", "webapp", "-b", "0.0.0.0:8000", "app:app"]
