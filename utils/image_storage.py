"""
이미지 저장 및 관리 유틸리티
"""
import os
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from PIL import Image
import io
from google.cloud import storage

logger = logging.getLogger(__name__)

# 이미지 저장 디렉토리 설정
UPLOAD_DIR = Path("uploads")
IMAGES_DIR = UPLOAD_DIR / "images"
THUMBNAILS_DIR = UPLOAD_DIR / "thumbnails"

# 지원하는 이미지 형식
SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}

# 구글 클라우드 버킷 환경변수
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")

def save_image_to_gcs(file_bytes, file_name, user_id):
    client = storage.Client()
    bucket = client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(f"images/{user_id}/{file_name}")
    blob.upload_from_string(file_bytes)
    blob.make_public()  # 또는 signed URL 사용
    return blob.public_url


def ensure_directories():
    """필요한 디렉토리들을 생성"""
    for directory in [UPLOAD_DIR, IMAGES_DIR, THUMBNAILS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"디렉토리 확인/생성: {directory}")

def generate_image_filename(original_filename: str, user_id: str) -> str:
    """이미지 파일명 생성"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    extension = Path(original_filename).suffix.lower()
    
    if extension not in SUPPORTED_FORMATS:
        extension = '.jpg'  # 기본값
    
    return f"{user_id}_{timestamp}_{unique_id}{extension}"

def save_image(image_bytes: bytes, original_filename: str, user_id: str) -> Optional[str]:
    """
    이미지를 저장하고 저장된 경로를 반환
    
    Args:
        image_bytes: 이미지 바이트 데이터
        original_filename: 원본 파일명
        user_id: 사용자 ID
        
    Returns:
        저장된 이미지의 상대 경로 또는 None (실패 시)
    """
    try:
        ensure_directories()
        
        # 파일명 생성
        filename = generate_image_filename(original_filename, user_id)
        file_path = IMAGES_DIR / filename
        
        # 이미지 저장
        with open(file_path, 'wb') as f:
            f.write(image_bytes)
        
        # 썸네일 생성 (선택사항)
        create_thumbnail(file_path, filename)
        
        # 상대 경로 반환 (DB 저장용)
        relative_path = str(file_path.relative_to(Path.cwd()))
        logger.info(f"이미지 저장 완료: {relative_path}")
        
        return relative_path
        
    except Exception as e:
        logger.error(f"이미지 저장 실패: {e}")
        return None

def create_thumbnail(original_path: Path, filename: str, size: tuple = (300, 300)) -> Optional[str]:
    """썸네일 이미지 생성"""
    try:
        # 원본 이미지 로드
        with Image.open(original_path) as img:
            # RGB로 변환 (RGBA 등 처리)
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # 썸네일 생성
            img.thumbnail(size, Image.Resampling.LANCZOS)
            
            # 썸네일 저장
            thumbnail_path = THUMBNAILS_DIR / f"thumb_{filename}"
            img.save(thumbnail_path, 'JPEG', quality=85)
            
            relative_path = str(thumbnail_path.relative_to(Path.cwd()))
            logger.info(f"썸네일 생성 완료: {relative_path}")
            
            return relative_path
            
    except Exception as e:
        logger.error(f"썸네일 생성 실패: {e}")
        return None

def get_image_url(file_path: str) -> str:
    """파일 경로를 웹 URL로 변환"""
    if not file_path:
        return ""
    
    # 상대 경로를 웹 경로로 변환
    if file_path.startswith('uploads/'):
        return f"/static/{file_path}"
    
    return file_path

def delete_image(file_path: str) -> bool:
    """이미지 파일 삭제"""
    try:
        if not file_path:
            return True
        
        # 메인 이미지 삭제
        main_path = Path(file_path)
        if main_path.exists():
            main_path.unlink()
            logger.info(f"이미지 삭제 완료: {file_path}")
        
        # 썸네일 삭제
        filename = main_path.name
        thumbnail_path = THUMBNAILS_DIR / f"thumb_{filename}"
        if thumbnail_path.exists():
            thumbnail_path.unlink()
            logger.info(f"썸네일 삭제 완료: {thumbnail_path}")
        
        return True
        
    except Exception as e:
        logger.error(f"이미지 삭제 실패: {e}")
        return False

def get_image_info(file_path: str) -> dict:
    """이미지 정보 반환"""
    try:
        if not file_path or not Path(file_path).exists():
            return {"error": "파일이 존재하지 않습니다"}
        
        with Image.open(file_path) as img:
            return {
                "size": img.size,
                "format": img.format,
                "mode": img.mode,
                "file_size": Path(file_path).stat().st_size
            }
    except Exception as e:
        return {"error": str(e)}
