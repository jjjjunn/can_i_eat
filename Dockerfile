# 1단계: 기본 이미지 선택
FROM python:3.12-slim

# 추가: 필수 패키지 설치 (Nginx 리버스 프록시 사용)
RUN apt-get update && apt-get install -y \
    nginx \
    supervisor \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 2단계: 작업 디렉터리 설정
WORKDIR /app

# 3단계: 종속성 파일 복사 및 설치
COPY requirements.txt .

# pip 설치 최적화 및 재시도 로직 추가 (더 안정적)
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --timeout 600 --retries 5 --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r requirements.txt

# 4단계: 소스 코드 복사
COPY . .

# 추가: Nginx 설정 복사
COPY nginx.conf /etc/nginx/nginx.conf

# 5단계: supervisord 설정 파일 복사
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# 추가: 로그 디렉토리 및 임시 디렉토리 생성
RUN mkdir -p /var/log/supervisor /app/uploads /var/log/nginx \
    /tmp/client_temp /tmp/proxy_temp_path /tmp/fastcgi_temp \
    /tmp/uwsgi_temp /tmp/scgi_temp && \
    chmod 755 /var/log/supervisor && \
    chmod 755 /app/uploads && \
    chmod 755 /var/log/nginx

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV LOG_LEVEL=INFO
ENV PORT=8080

# 6단계: 포트 노출
EXPOSE $PORT

# 7단계: 시작 스크립트 실행 권한 부여
RUN chmod +x /app/start.sh

# 8단계: 애플리케이션 실행 명령어 설정
CMD ["/app/start.sh"]