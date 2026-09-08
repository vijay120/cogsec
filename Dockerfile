# CogSec Tracker — container image for Fly.io.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    COGSEC_DB=/data/cogsec.db

WORKDIR /srv

COPY app/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Mount point for the Fly volume. Created here too so the image still boots
# without one (it just won't persist).
RUN mkdir -p /data

EXPOSE 8080

# server.py does `import db` / `import charts`, so app/ has to be the working
# directory. One worker: SQLite behind a single writer avoids lock contention,
# and threads are plenty for a single-user tracker.
CMD ["gunicorn", "--chdir", "/srv/app", "--bind", "0.0.0.0:8080", \
     "--workers", "1", "--threads", "4", "--timeout", "60", \
     "--access-logfile", "-", "server:app"]
