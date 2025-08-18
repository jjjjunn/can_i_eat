import os
import logging
from typing import Optional
from uuid import uuid4

import httpx
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

# 로컬 프로젝트 DB, 컨트롤러
from database.database import get_db
from controllers.users_controllers import create_or_update_social_user

# 공통 함수 import
from utils.utils import verify_jwt_token, create_jwt_token

# 환경변수는 시작 시점에서 env_loader.py에 의해 중앙 관리됩니다.

router = APIRouter()

# 구조화된 로깅 설정 강화
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
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

KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")
KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET")
KAKAO_REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI")

STREAMLIT_APP_URL = os.getenv("STREAMLIT_APP_URL")

# 로깅 추가 - 환경변수 확인
logger.info(f"🔍 OAuth 환경변수 확인:")
logger.info(f"  - GOOGLE_REDIRECT_URI: {GOOGLE_REDIRECT_URI}")
logger.info(f"  - KAKAO_REDIRECT_URI: {KAKAO_REDIRECT_URI}")

# 환경 변수 검증 - 수정된 버전
def validate_oauth_config():
    """OAuth 설정 검증 - 실패시 앱 시작 중단"""
    missing_vars = []
    
    # Google OAuth 설정 확인
    if not GOOGLE_CLIENT_ID:
        missing_vars.append("GOOGLE_CLIENT_ID")
    if not GOOGLE_CLIENT_SECRET:
        missing_vars.append("GOOGLE_CLIENT_SECRET")
    if not GOOGLE_REDIRECT_URI:
        missing_vars.append("GOOGLE_REDIRECT_URI")
    
    # Kakao OAuth 설정 확인
    if not KAKAO_REST_API_KEY:
        missing_vars.append("KAKAO_REST_API_KEY")
    if not KAKAO_CLIENT_SECRET:
        missing_vars.append("KAKAO_CLIENT_SECRET")
    if not KAKAO_REDIRECT_URI:
        missing_vars.append("KAKAO_REDIRECT_URI")
    
    if missing_vars:
        error_msg = f"❌ 누락된 OAuth 환경 변수: {missing_vars}"
        logger.warning(error_msg)
        logger.warning("⚠️ OAuth 기능이 제한적으로 작동할 수 있습니다.")
        return False
    
    # ✅ redirect_uri 유효성 검사 추가
    if GOOGLE_REDIRECT_URI and not GOOGLE_REDIRECT_URI.startswith('https://'):
        logger.warning(f"⚠️ Google redirect_uri가 HTTPS가 아닙니다: {GOOGLE_REDIRECT_URI}")
    
    if KAKAO_REDIRECT_URI and not KAKAO_REDIRECT_URI.startswith('https://'):
        logger.warning(f"⚠️ Kakao redirect_uri가 HTTPS가 아닙니다: {KAKAO_REDIRECT_URI}")
    
    logger.info("✅ OAuth 환경 변수 설정 완료")
    logger.info(f"  Google redirect: {GOOGLE_REDIRECT_URI}")
    logger.info(f"  Kakao redirect: {KAKAO_REDIRECT_URI}")
    return True

# 앱 시작 시 환경 변수 검증 - 실패시에도 앱 시작 허용
try:
    validate_oauth_config()
except Exception as e:
    logger.warning(f"OAuth 설정 검증 중 오류 발생: {e}")
    logger.warning("⚠️ OAuth 기능이 제한적으로 작동할 수 있습니다.")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

SUPPORTED_PROVIDERS = {"google", "kakao"}

@router.get("/auth/login/{provider}")
async def login(provider: str, request: Request):
    """OAuth 로그인 시작"""
    logger.info(f"🚀 OAuth 로그인 시작: provider={provider}")
    
    if provider not in SUPPORTED_PROVIDERS:
        logger.warning(f"⚠️ 지원하지 않는 프로바이더: {provider}")
        raise HTTPException(status_code=400, detail="Unsupported provider")

    state = str(uuid4())
    request.session["oauth_state"] = state  # 세션 저장
    logger.info(f"✅ OAuth state 생성 및 세션 저장: {state[:8]}...")

    if provider == "google":
        redirect_url = (
            f"{GOOGLE_AUTH_URL}?"
            f"client_id={GOOGLE_CLIENT_ID}&"
            f"redirect_uri={GOOGLE_REDIRECT_URI}&"
            f"response_type=code&"
            f"scope=openid%20email%20profile&"
            f"state={state}"
        )
        logger.info(f"🔗 Google OAuth URL 생성: {GOOGLE_REDIRECT_URI}")
        
    elif provider == "kakao":
        redirect_url = (
            f"{KAKAO_AUTH_URL}?"
            f"client_id={KAKAO_REST_API_KEY}&"
            f"redirect_uri={KAKAO_REDIRECT_URI}&"
            f"response_type=code&"
            f"state={state}"
        )
        logger.info(f"🔗 Kakao OAuth URL 생성: {KAKAO_REDIRECT_URI}")

    logger.info(f"↗️ OAuth 리디렉션: {redirect_url[:100]}...")
    return RedirectResponse(redirect_url)


@router.get("/auth/{provider}/callback")
async def auth_callback(
    provider: str,
    code: str,
    state: Optional[str] = None,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """OAuth 콜백 처리 - 강화된 로깅 및 에러 처리"""
    logger.info(f"📞 OAuth 콜백 받음: provider={provider}, code={'있음' if code else '없음'}, state={state[:8] if state else '없음'}...")
    
    # 필수 환경 변수 확인
    if provider == "google" and not all([GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI]):
        logger.error("❌ Google OAuth 환경 변수가 설정되지 않았습니다")
        raise HTTPException(status_code=500, detail="Google OAuth 설정이 완료되지 않았습니다")
    
    if provider == "kakao" and not all([KAKAO_REST_API_KEY, KAKAO_CLIENT_SECRET, KAKAO_REDIRECT_URI]):
        logger.error("❌ Kakao OAuth 환경 변수가 설정되지 않았습니다")
        raise HTTPException(status_code=500, detail="Kakao OAuth 설정이 완료되지 않았습니다")
    
    if provider not in SUPPORTED_PROVIDERS:
        logger.error(f"❌ 지원하지 않는 프로바이더: {provider}")
        raise HTTPException(status_code=400, detail="Unsupported provider")

    # state 검증 (강화)
    saved_state = request.session.get("oauth_state")
    logger.info(f"🔍 State 검증: saved={saved_state[:8] if saved_state else '없음'}, received={state[:8] if state else '없음'}")
    
    if saved_state and state != saved_state:
        logger.error(f"❌ State 불일치: saved={saved_state}, received={state}")
        raise HTTPException(status_code=400, detail="Invalid state - CSRF 보호")

    # Access Token 요청 준비
    if provider == "google":
        token_url = GOOGLE_TOKEN_URL
        token_data = {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        logger.info(f"🔑 Google 토큰 요청 준비: redirect_uri={GOOGLE_REDIRECT_URI}")
        
    elif provider == "kakao":
        token_url = KAKAO_TOKEN_URL
        token_data = {
            "code": code,
            "client_id": KAKAO_REST_API_KEY,
            "client_secret": KAKAO_CLIENT_SECRET,
            "redirect_uri": KAKAO_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        logger.info(f"🔑 Kakao 토큰 요청 준비: redirect_uri={KAKAO_REDIRECT_URI}")
        logger.info(f"🔍 환경변수 확인: client_id={'설정됨' if KAKAO_REST_API_KEY else '없음'}, secret={'설정됨' if KAKAO_CLIENT_SECRET else '없음'}")

    # 타임아웃 설정 증가 및 재시도 로직
    timeout = httpx.Timeout(60.0, connect=15.0)  # 타임아웃 증가
    
    for attempt in range(3):  # 최대 3회 재시도
        try:
            logger.info(f"🌐 토큰 요청 시도 {attempt + 1}/3: {token_url}")
            
            async with httpx.AsyncClient(
                timeout=timeout,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            ) as client:
                
                # 요청 헤더 추가
                headers = {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                    "User-Agent": "FoodAnalyzer/2.0"
                }
                
                token_res = await client.post(
                    token_url, 
                    data=token_data,
                    headers=headers
                )
                
                logger.info(f"📡 토큰 응답 상태: {token_res.status_code}")
                
                if token_res.status_code == 200:
                    tokens = token_res.json()
                    access_token = tokens.get("access_token")
                    logger.info(f"✅ 액세스 토큰 획득 성공: {'있음' if access_token else '없음'}")
                    break
                else:
                    error_detail = token_res.text
                    logger.error(f"❌ 토큰 요청 실패 (시도 {attempt + 1}): {token_res.status_code} - {error_detail}")
                    
                    if attempt == 2:  # 마지막 시도
                        raise HTTPException(
                            status_code=400, 
                            detail=f"OAuth 토큰 획득 실패: {token_res.status_code} - {error_detail}"
                        )
                        
        except httpx.TimeoutException as e:
            logger.error(f"⏱️ 토큰 요청 타임아웃 (시도 {attempt + 1}): {str(e)}")
            if attempt == 2:
                logger.error("❌ 최대 재시도 횟수 초과 - 타임아웃")
                raise HTTPException(status_code=504, detail="OAuth 서버 응답 시간 초과 - 잠시 후 다시 시도해주세요")
                
        except httpx.ConnectError as e:
            logger.error(f"🔌 연결 오류 (시도 {attempt + 1}): {str(e)}")
            if attempt == 2:
                logger.error("❌ 최대 재시도 횟수 초과 - 연결 실패")
                raise HTTPException(status_code=502, detail="OAuth 서버 연결 실패 - 잠시 후 다시 시도해주세요")
                
        except Exception as e:
            logger.error(f"💥 예상치 못한 오류 (시도 {attempt + 1}): {type(e).__name__}: {str(e)}")
            if attempt == 2:
                logger.error("❌ 최대 재시도 횟수 초과 - 예상치 못한 오류")
                raise HTTPException(status_code=500, detail="OAuth 처리 중 내부 오류 - 잠시 후 다시 시도해주세요")

    # 사용자 정보 요청
    logger.info(f"👤 사용자 정보 요청 시작: {provider}")
    
    if provider == "google":
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                userinfo_res = await client.get(
                    GOOGLE_USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                userinfo_res.raise_for_status()
                profile = userinfo_res.json()
                user_id = profile.get("id")
                nickname = profile.get("name", "User")
                email = profile.get("email")
                logger.info(f"✅ Google 사용자 정보 획득: id={user_id}, email={email}")
                
        except Exception as e:
            logger.error(f"❌ Google 사용자 정보 요청 실패: {str(e)}")
            raise HTTPException(status_code=502, detail=f"Google 사용자 정보 획득 실패: {str(e)}")

    elif provider == "kakao":
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                userinfo_res = await client.get(
                    KAKAO_USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                userinfo_res.raise_for_status()
                profile = userinfo_res.json()
                user_id = profile.get("id")
                nickname = profile.get("properties", {}).get("nickname", "User")
                email = profile.get("kakao_account", {}).get("email")
                logger.info(f"✅ Kakao 사용자 정보 획득: id={user_id}, email={email}")
                
        except Exception as e:
            logger.error(f"❌ Kakao 사용자 정보 요청 실패: {str(e)}")
            raise HTTPException(status_code=502, detail=f"Kakao 사용자 정보 획득 실패: {str(e)}")

    # DB에 사용자 정보 저장
    logger.info(f"💾 사용자 정보 DB 저장 시작")
    try:
        user = create_or_update_social_user(
            db=db,
            user_info={
                "provider_id": str(user_id),
                "email": email,
                "name": nickname
            },
            provider=provider,
            request=request,
            access_token=access_token
        )
        logger.info(f"✅ 사용자 정보 DB 저장 완료")
    except Exception as e:
        logger.error(f"❌ 사용자 DB 저장 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="사용자 정보 저장 실패")

    # JWT 발급
    try:
        jwt_token = create_jwt_token({
            "sub": str(user_id),
            "provider_id": str(user_id),
            "nickname": nickname,
            "email": email,
            "provider": provider
        })
        logger.info(f"✅ JWT 토큰 생성 완료")
    except Exception as e:
        logger.error(f"❌ JWT 토큰 생성 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="인증 토큰 생성 실패")

    # state 정리
    request.session.pop("oauth_state", None)

    # Streamlit 앱으로 리디렉션
    if STREAMLIT_APP_URL:
        redirect_url = f"{STREAMLIT_APP_URL}?token={jwt_token}&login=success"
        logger.info(f"🎯 Streamlit 앱으로 리디렉션: {STREAMLIT_APP_URL}")
        return RedirectResponse(url=redirect_url, status_code=303)
    else:
        logger.warning("⚠️ STREAMLIT_APP_URL이 설정되지 않아 JSON 응답을 반환")
        return JSONResponse({
            "success": True,
            "message": "로그인 성공",
            "token": jwt_token,
            "user": {
                "id": str(user_id),
                "nickname": nickname,
                "email": email,
                "provider": provider
            }
        })

# 헬스체크
@router.get("/auth/health")
async def health():
    return JSONResponse({"ok": True})

@router.get("/verify-token")
def verify_token_endpoint(token: str = None):
    """JWT 토큰 검증 엔드포인트 (디버깅용)"""
    try:
        if not token:
            return {
                "valid": False, 
                "error": "토큰이 제공되지 않았습니다",
                "debug_info": "URL 파라미터로 token을 제공해주세요"
            }
        
        payload = verify_jwt_token(token)
        return {
            "valid": True, 
            "user": payload,
            "debug_info": {
                "token_length": len(token),
                "algorithm": JWT_ALGORITHM,
                "secret_key_length": len(JWT_SECRET_KEY)
            }
        }
    except HTTPException as e:
        return {
            "valid": False, 
            "error": e.detail,
            "debug_info": {
                "token_provided": bool(token),
                "token_length": len(token) if token else 0,
                "algorithm": JWT_ALGORITHM,
                "secret_key_length": len(JWT_SECRET_KEY)
            }
        }
        
# 토큰 테스트용 엔드포인트
@router.get("/test-jwt")
def test_jwt_creation():
    """JWT 토큰 생성 테스트용 엔드포인트"""
    try:
        test_payload = {
            "sub": "test-user-123",
            "email": "test@example.com",
            "name": "Test User"
        }
        
        token = create_jwt_token(test_payload)
        verified = verify_jwt_token(token)
        
        return {
            "success": True,
            "token_created": True,
            "token_verified": True,
            "token_length": len(token),
            "payload": verified,
            "debug": {
                "secret_key_length": len(JWT_SECRET_KEY),
                "algorithm": JWT_ALGORITHM
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "debug": {
                "secret_key_length": len(JWT_SECRET_KEY),
                "algorithm": JWT_ALGORITHM
            }
        }

# 로그인 상태 확인 (세션 기반)
@router.get("/status")
def get_auth_status(request: Request):
    """현재 로그인 상태 확인"""
    if request.session.get('is_logged_in'):
        return {
            "logged_in": True,
            "user_id": request.session.get('id'),
            "name": request.session.get('name'),
            "email": request.session.get('email'),
            "provider": request.session.get('provider')
        }
    return {"logged_in": False}