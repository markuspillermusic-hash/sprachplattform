FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --requirement requirements.txt

COPY . .
RUN mkdir -p /app/var/audio /app/staticfiles \
    && DJANGO_SECRET_KEY=build-only-not-for-runtime python manage.py collectstatic --noinput

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app/var /app/staticfiles
USER appuser

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60"]
