FROM python:3.11-slim
WORKDIR /app

COPY dash/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY dash/app.py /app/app.py

ENV PYTHONUNBUFFERED=1
EXPOSE 8050
CMD ["python", "/app/app.py"]
