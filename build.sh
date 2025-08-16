#!/bin/bash

# Docker 빌드 스크립트
set -e

echo "🚀 Docker 빌드 시작..."

# 환경 변수 설정
IMAGE_NAME="can-i-eat-st"
TAG="latest"

# 기존 이미지 정리 (선택사항)
echo "🧹 기존 이미지 정리 중..."
docker system prune -f

# 안정적인 Dockerfile 사용
echo "📦 Docker 이미지 빌드 중..."
docker build \
    --no-cache \
    --progress=plain \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    -t ${IMAGE_NAME}:${TAG} \
    -f Dockerfile.stable \
    .

echo "✅ 빌드 완료!"
echo "이미지: ${IMAGE_NAME}:${TAG}"

# 빌드된 이미지 정보 출력
echo "📊 이미지 정보:"
docker images ${IMAGE_NAME}:${TAG}
