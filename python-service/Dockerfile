FROM python:3.12-slim

# Run as non-root for defense in depth
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/sh appuser    

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY core/ core/
COPY services/ services/
COPY main.py .

# Drop privileges — the service needs no root capabilities
USER appuser

# Multi-service configuration (JSON array)
# SERVICES_CONFIG='[{"device_id":"wifi-guest","type":"wifi_ssid","name":"Guest WiFi","config":{"wlan_id":"uuid"}}]'
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
