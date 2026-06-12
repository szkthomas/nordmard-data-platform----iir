# =============================================================================
#  ETL szolgáltatás image — könnyűsúlyú Python ELT motor
# =============================================================================
FROM python:3.12-slim

# Determinisztikus, buffermentes naplózás
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Europe/Budapest

WORKDIR /app

# Függőségek külön rétegben (jobb build cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Alkalmazás-kód
COPY . .

# A pipeline folyamatosan fut (long-running szolgáltatás)
CMD ["python", "-u", "pipeline.py"]
