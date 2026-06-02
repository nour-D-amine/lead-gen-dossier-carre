FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

# Installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# S'assurer que Chromium est installé et configuré pour Playwright
RUN playwright install chromium

# Copier le code de l'application
COPY . .

# Exposer le port de l'application
EXPOSE 8080

# Commande de démarrage
CMD uvicorn server:app --host 0.0.0.0 --port ${PORT:-8080}
