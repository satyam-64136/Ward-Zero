FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 WARDZERO_DB=/data/wardzero.db
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn==22.0.0

COPY app.py risk.py simulator.py ./
COPY templates templates
COPY static static

# Run as a non-root user; /data holds the database, /sim holds the simulator's offline buffer.
RUN useradd --system --uid 10001 wardzero && mkdir /data /sim && chown wardzero /data /sim
USER wardzero
VOLUME ["/data"]
EXPOSE 5000

HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/health', timeout=2)"

# One worker on purpose: the demo control state (SIM) lives in process memory.
CMD ["gunicorn", "--workers", "1", "--threads", "4", "--bind", "0.0.0.0:5000", "app:app"]
