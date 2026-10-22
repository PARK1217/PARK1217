# 냉장고 사전 — 단일 컨테이너. SQLite는 /data 볼륨.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY static ./static
COPY legacy ./legacy
COPY data ./data

# 컨테이너 안 포트는 8080 고정. 바깥 포트는 compose의 HOST_PORT로 바꾼다.
ENV PORT=8080 \
    DB_PATH=/data/fridge.db \
    DATA_DIR=/app/data \
    TZ=Asia/Seoul

RUN mkdir -p /data
VOLUME ["/data"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=2).status == 200 else 1)"

CMD ["python", "-m", "app"]
