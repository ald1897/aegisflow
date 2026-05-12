FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -e .

EXPOSE 8040

CMD ["uvicorn", "aegisflow_evaluation_service.main:app", "--host", "0.0.0.0", "--port", "8040"]
