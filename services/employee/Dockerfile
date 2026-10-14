FROM python:3.13-slim
WORKDIR /app
COPY requirements.lock ./requirements.lock
RUN pip install --no-cache-dir -r requirements.lock && useradd --create-home --uid 10001 employee
COPY --chown=employee:employee . .
USER employee
EXPOSE 8020
CMD ["sh", "-c", "alembic upgrade head && python -m uvicorn app.main:app --host 0.0.0.0 --port 8020 --no-access-log"]
