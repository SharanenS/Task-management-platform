FROM python:3.13-slim
WORKDIR /app
COPY requirements.lock ./requirements.lock
RUN pip install --no-cache-dir -r requirements.lock && useradd --create-home --uid 10001 notification
COPY --chown=notification:notification . .
USER notification
EXPOSE 8060
CMD ["sh", "-c", "alembic upgrade head && python -m uvicorn app.main:app --host 0.0.0.0 --port 8060 --no-access-log"]
