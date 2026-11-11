FROM python:3.13-slim

# GeoDjango needs GEOS + GDAL (+ PROJ) system libraries.
RUN apt-get update \
    && apt-get install -y --no-install-recommends binutils libproj-dev gdal-bin libgeos-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-install-project

COPY . .
# Placeholder only satisfies the settings guard; collectstatic signs nothing.
RUN DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput
RUN useradd --create-home app && chown -R app /app
USER app

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
