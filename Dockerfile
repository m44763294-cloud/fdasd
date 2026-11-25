FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=8080

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY run.py ./
COPY app ./app
COPY web ./web
COPY preview_welcome.png ./

RUN mkdir -p data
VOLUME ["/app/data"]

EXPOSE 8080
CMD ["python", "run.py"]
