#!/bin/bash

# 컨테이너 시작 스크립트
set -e

echo "🚀 컨테이너 시작 중..."

# 환경 변수 확인
echo "📋 환경 변수 확인 중..."
if [ -z "$JWT_SECRET_KEY" ]; then
    echo "⚠️ JWT_SECRET_KEY가 설정되지 않았습니다."
fi

if [ -z "$DATABASE_URL" ]; then
    echo "⚠️ DATABASE_URL이 설정되지 않았습니다."
fi

# 디렉토리 권한 확인
echo "📁 디렉토리 권한 확인 중..."
chmod 755 /app/uploads
chmod 755 /var/log/supervisor
chmod 755 /var/log/nginx

# Nginx 설정 테스트
echo "🌐 Nginx 설정 테스트 중..."
nginx -t

# Supervisord 시작
echo "🎯 Supervisord 시작 중..."
exec /usr/bin/supervisord -n -c /etc/supervisor/conf.d/supervisord.conf