from fastapi import Depends, HTTPException, Header
from typing import Dict, Any
from dotenv import load_dotenv
import jwt
import logging
import os
from datetime import datetime, timedelta
from sqlmodel import Session
from uuid import UUID
from database.database import engine
import streamlit as st

from utils.app_classes import SessionStateManager, ServiceInitializer

# 공통으로 쓰여지는 함수 모임

# 환경변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OAuth Endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

KAKAO_AUTH_URL = "https://kauth.kakao.com/oauth/authorize"
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USERINFO_URL = "https://kapi.kakao.com/v2/user/me"

# 환경변수
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

KAKAO_CLIENT_ID = os.getenv("KAKAO_REST_API_KEY")
KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET")
KAKAO_REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI")

STREAMLIT_APP_URL = os.getenv("STREAMLIT_APP_URL")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

SUPPORTED_PROVIDERS = {"google", "kakao"}

def initialize_app():
    """앱 초기화"""
    SessionStateManager.initialize()
    
    if not st.session_state.get('initialization_complete', False):
        st.info("시스템을 초기화하고 있습니다...")
        
        if not ServiceInitializer.initialize_all_services():
            st.error("시스템 초기화에 실패했습니다.")
            st.stop()
            
        st.session_state.initialization_complete = True
        st.success("시스템 초기화 완료!")
        st.rerun()


# 의존성 주입 함수들
def get_session():
    """데이터베이스 세션 의존성"""
    with Session(engine) as session:
        yield session

def validate_user_id(header_user_id: str = Header(..., alias="X-User-Id", description="사용자 인증 ID")):
    """사용자 ID 검증"""
    # 실제 환경에서는 JWT 토큰 검증 등의 로직 추가
    return header_user_id

# JWT 토큰 생성
def create_jwt_token(payload: dict) -> str:
    """JWT 토큰 생성 (디버깅 로그 포함)"""
    try:
        # 현재 시간과 만료 시간 설정
        now = datetime.utcnow()
        expire = now + timedelta(minutes=JWT_EXPIRE_MINUTES)
        
        # payload에 기본 클레임 추가
        token_payload = {
            **payload,
            "iat": now,  # 발행 시간
            "exp": expire,  # 만료 시간
            "iss": "food-analyzer-api",  # 발행자
        }
        
        logger.info(f"JWT 토큰 생성 중...")
        logger.info(f"Payload: {token_payload}")
        logger.info(f"Secret Key 길이: {len(JWT_SECRET_KEY)}")
        
        # 토큰 생성
        token = jwt.encode(token_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        
        logger.info(f"JWT 토큰 생성 성공. 토큰 길이: {len(token)}")
        logger.info(f"토큰 앞부분: {token[:50]}...")
        
        return token

    except Exception as e:
        logger.error(f"JWT 토큰 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=f"토큰 생성 실패: {str(e)}")



# JWT 토큰 검증
def verify_jwt_token(token: str) -> Dict[str, Any]:
    """JWT 토큰 검증 (상세한 디버깅 로그 포함)"""
    try:
        logger.info(f"JWT 토큰 검증 시작...")
        logger.info(f"받은 토큰 길이: {len(token) if token else 0}")
        
        if not token:
            raise HTTPException(status_code=401, detail="토큰이 제공되지 않았습니다")
        
        # 토큰 앞부분 로깅 (보안상 전체는 로깅하지 않음)
        logger.info(f"토큰 앞부분: {token[:50]}...")
        logger.info(f"Secret Key 길이: {len(JWT_SECRET_KEY)}")
        
        # 토큰 디코딩
        payload = jwt.decode(
            token, 
            JWT_SECRET_KEY, 
            algorithms=[JWT_ALGORITHM],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True
            }
        )
        
        logger.info(f"JWT 토큰 검증 성공")
        logger.info(f"Payload: {payload}")
        
        return payload
        
    except jwt.ExpiredSignatureError as e:
        logger.error(f"토큰 만료: {e}")
        raise HTTPException(status_code=401, detail="토큰이 만료되었습니다")
    except jwt.InvalidTokenError as e:
        logger.error(f"유효하지 않은 토큰: {e}")
        raise HTTPException(status_code=401, detail=f"유효하지 않은 토큰입니다: {str(e)}")
    except jwt.DecodeError as e:
        logger.error(f"토큰 디코딩 오류: {e}")
        raise HTTPException(status_code=401, detail="토큰 형식이 올바르지 않습니다")
    except Exception as e:
        logger.error(f"토큰 검증 중 예상치 못한 오류: {e}")
        raise HTTPException(status_code=401, detail=f"토큰 검증 실패: {str(e)}")