FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# P5: Install system deps for bcrypt
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    sed '/^reportlab==/d' requirements.txt > /tmp/requirements-base.txt && \
    pip install \
    --no-cache-dir \
    --retries 8 \
    --timeout 600 \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    -r /tmp/requirements-base.txt && \
    pip install \
    --no-cache-dir \
    --no-deps \
    --retries 8 \
    --timeout 600 \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    reportlab==4.4.3

COPY . .

# Ensure migration and persistent-volume mount points exist with app ownership.
# Docker copies this ownership into a newly created named volume.
RUN mkdir -p migrations/versions data/park_documents data/policy_snapshots

RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/ready', timeout=3)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
