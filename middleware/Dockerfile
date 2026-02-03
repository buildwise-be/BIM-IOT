FROM python:3.11-slim
WORKDIR /app

COPY middleware/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY middleware/app.py /app/app.py
COPY middleware/__init__.py /app/__init__.py

RUN mkdir -p /app/mapping
COPY frontend/src/data/devices.ifc.json /app/mapping/devices.ifc.json

ENV DEVICE_MAPPING_PATH=/app/mapping/devices.ifc.json
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["python", "/app/app.py"]
