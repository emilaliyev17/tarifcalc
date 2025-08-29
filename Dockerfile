FROM python:3.11-slim

WORKDIR /app

# Install PostgreSQL dependencies
RUN apt-get update && apt-get install -y     gcc     libpq-dev     && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

EXPOSE 8000

# Create start script that runs migrations and creates admin
RUN echo '#!/bin/sh
python manage.py migrate
python manage.py shell << EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username="admin").exists():
    User.objects.create_superuser("admin", "admin@example.com", "Admin123!")
    print("Admin user created")
EOF
exec gunicorn core.wsgi:application --bind 0.0.0.0:8000' > /app/start.sh && chmod +x /app/start.sh

CMD ["/app/start.sh"]