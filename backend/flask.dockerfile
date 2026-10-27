FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=run.py

WORKDIR /app

RUN addgroup --system appgroup && adduser --system --ingroup appgroup --home /home/appuser appuser

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appgroup . .
USER appuser

EXPOSE 4000

CMD ["sh", "-c", "flask db upgrade && flask seed && exec gunicorn --workers 4 --bind 0.0.0.0:4000 run:app"]
