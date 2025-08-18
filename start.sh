#!/bin/bash
set -e

echo "🚀 FastAPI 단독 시작..."

# 포트 설정
export PORT=${PORT:-8081}
echo "포트: $PORT"

# 필수 디렉토리 생성
mkdir -p /app/uploads

cd /app

# FastAPI만 시작 (nginx 없이)
exec uvicorn main:app --host 0.0.0.0 --port $PORT --log-level info