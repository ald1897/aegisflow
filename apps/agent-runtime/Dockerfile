FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY apps/agent-runtime/pyproject.toml ./
COPY apps/agent-runtime/src ./src
COPY prompts ./prompts
RUN pip install --no-cache-dir -e .

EXPOSE 8010

CMD ["uvicorn", "aegisflow_agent_runtime.main:app", "--host", "0.0.0.0", "--port", "8010"]
