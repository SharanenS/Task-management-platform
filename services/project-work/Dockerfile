FROM python:3.13.5-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY --from=security taskspace_security ./taskspace_security
COPY . .
RUN useradd --system --uid 10001 service
USER service
EXPOSE 8000
CMD ["uvicorn", "project_work.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
