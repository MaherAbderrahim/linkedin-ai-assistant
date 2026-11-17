# Déploiement cloud (qualification Northflank) : image Python stdlib du bot.
# Aucun secret dans l'image : le jeton Telegram et les identifiants viennent
# de variables d'environnement injectées par la plateforme au démarrage.
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
COPY deploy/entrypoint.py /app/entrypoint.py

# /data est le point de montage du volume persistant (base SQLite + config).
VOLUME /data
ENTRYPOINT ["python", "/app/entrypoint.py"]
