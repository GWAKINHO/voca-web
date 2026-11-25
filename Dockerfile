# 학교 서버용 이미지 (R-01~R-16, 「Dockerfile 구성」 참고)
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DB_PATH=/data/voca.db

WORKDIR /app

# UID 10001 사용자 생성, 쓰기 가능한 /data 준비 (named volume 이 이 소유자를 물려받는다)
RUN groupadd --gid 10001 app \
 && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app \
 && mkdir -p /data \
 && chown 10001:10001 /data

# 의존성을 먼저 설치해 캐시를 살린다 (R-13)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

USER 10001:10001

# 운영용 서버 실행, 0.0.0.0:8080 에서 듣는다 (R-03, R-14, R-15)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "app:app"]
