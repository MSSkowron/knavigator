FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY exporter.py .

# Domyślne wartości - mogą być nadpisane przez zmienne środowiskowe w K8s
ENV LISTEN_PORT=8000
ENV SCRAPE_INTERVAL=15
ENV LOG_LEVEL=INFO
# ENV TARGET_NAMESPACE="" # Pozostaw puste dla cluster-wide

EXPOSE 8000

CMD ["python", "exporter.py"]
