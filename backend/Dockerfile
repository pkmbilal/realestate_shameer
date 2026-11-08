FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# GDAL, GEOS and PROJ are required by GeoDjango (PostGIS support).
# Pango, HarfBuzz and the Noto fonts let WeasyPrint print Arabic invoices (joined letters, RTL).
RUN apt-get update \
    && apt-get install -y --no-install-recommends binutils libproj-dev gdal-bin \
       libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# local.txt for development; production builds pass --build-arg REQUIREMENTS=production.txt
ARG REQUIREMENTS=local.txt
COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/${REQUIREMENTS}

COPY . .

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
