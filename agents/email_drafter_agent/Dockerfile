FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

COPY agents/email_drafter_agent/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY .claude /app/.claude
COPY agents/email_drafter_agent/src /app/agents/email_drafter_agent/src
COPY agents/email_drafter_agent/__init__.py /app/agents/email_drafter_agent/__init__.py

ENV PYTHONPATH=/app/agents/email_drafter_agent
EXPOSE 8080
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
