FROM python:3.9-slim

ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=wsgi.py
ENV FLASK_ENV=production
ENV TEMP_UNIT=F

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data logs

EXPOSE 8087

CMD ["gunicorn", "--bind", "0.0.0.0:8087", "--workers", "2", "--threads", "2", "--timeout", "30", "--access-logfile", "-", "--error-logfile", "-", "wsgi:app"] 