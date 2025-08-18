import logging
import sys
import os
from uuid import UUID
from datetime import datetime
from fastapi import FastAPI, File, UploadFile, Depends, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from sqlmodel import Session, select

# 환경 변수 로더 import
from utils.env_loader import load_environment_variables

from database.database import engine, create_db_and_tables, get_db
from database.models import UserFoodLog
from services.ai_server import (
    perform_ocr_analysis,
    perform_chatbot_analysis_and_save,
    initialize_services
)
from models.schemas import (
    OcrResponse,
    AnalysisRequest,
    AnalysisResponse,
    FoodLogResponse,
    UserFoodLogsResponse,
    BaseResponse
)

from oauth import social_auth  # google, kakao

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "utils")))
from utils.utils import get_session, validate_user_id
from utils.image_storage import delete_image

# 환경 변수 로드 후 로깅 설정
load_environment_variables()

# 구조화된 로깅 설정 강화
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        # logging.FileHandler('/var/log/supervisor/fastapi_app.log')  # 필요시 활성화
    ]
)
logger = logging.getLogger(__name__)

# 전역 예외 처리 미들웨어 추가
class GlobalExceptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            logger.error(f"💥 처리되지 않은 예외: {type(exc).__name__}: {str(exc)}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"detail": "내부 서버 오류가 발생했습니다"}
            )

# FastAPI 앱 생성
app = FastAPI(
    title="Food Ingredient Analyzer API",
    version="2.0.0",
    description="AI 기반 음식 성분 분석 및 섭취 가이드 API",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 전역 예외 처리 미들웨어 추가
app.add_middleware(GlobalExceptionMiddleware)


# 요청 로깅 미들웨어 강화
@app.middleware("https")
async def enhanced_log_requests(request: Request, call_next):
    start_time = datetime.now()
    
    # 요청 상세 로깅
    client_ip = request.client.host if request.client else 'unknown'
    user_agent = request.headers.get('user-agent', 'unknown')
    
    logger.info(f"📥 Request: {request.method} {request.url.path} - IP: {client_ip} - UA: {user_agent[:50]}...")
    
    # OAuth 관련 요청 특별 로깅
    if '/auth/' in request.url.path:
        logger.info(f"🔐 OAuth 관련 요청: {request.url}")
        # 쿼리 파라미터 로깅 (민감 정보 제외)
        query_params = dict(request.query_params)
        safe_params = {k: v[:10] + '...' if len(str(v)) > 10 else v 
                      for k, v in query_params.items() 
                      if k not in ['code', 'access_token', 'refresh_token']}
        if safe_params:
            logger.info(f"📝 Query params: {safe_params}")
    
    try:
        response = await call_next(request)
        
        # 응답 로깅
        duration = datetime.now() - start_time
        status_icon = "✅" if response.status_code < 400 else "❌" if response.status_code < 500 else "💥"
        
        logger.info(f"📤 {status_icon} Response: {request.method} {request.url.path} - Status: {response.status_code} - Duration: {duration.total_seconds():.3f}s")
        
        # 에러 응답 특별 로깅
        if response.status_code >= 400:
            logger.warning(f"⚠️ Error Response: {response.status_code} for {request.method} {request.url.path}")
        
        return response
        
    except Exception as e:
        duration = datetime.now() - start_time
        logger.error(f"💥 Request failed: {request.method} {request.url.path} - Error: {str(e)} - Duration: {duration.total_seconds():.3f}s")
        raise

# 세션 미들웨어 설정 개선
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY") or os.getenv("JWT_SECRET_KEY")
if not SESSION_SECRET_KEY:
    logger.warning("⚠️ SESSION_SECRET_KEY가 설정되지 않았습니다. 랜덤 키를 생성합니다.")
    import secrets
    SESSION_SECRET_KEY = secrets.token_urlsafe(32)

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    session_cookie="food_analyzer_session",
    max_age=3600,  # 1시간
    same_site="lax",  # CSRF 보호
    https_only=True  # 개발환경에서는 False, 프로덕션에서는 True
)

# CORS 설정 개선
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",  # Streamlit 기본 포트
        "http://localhost:8081",  # FastAPI 개발 서버
        "https://can-i-eat-st-67955155645.asia-northeast3.run.app", # 프로덕션 도메인
        # 필요한 도메인들 추가
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# 정적 파일 서빙 (이미지 등)
if os.path.exists("uploads"):
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
else:
    logger.warning("⚠️ uploads 디렉토리가 존재하지 않습니다. 생성합니다.")
    os.makedirs("uploads", exist_ok=True)
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# 라우터 추가
app.include_router(social_auth.router)

STREAMLIT_APP_URL = os.getenv("STREAMLIT_APP_URL", "http://localhost:8501")

# JWT 설정
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# OAuth 제공자 목록
SUPPORTED_PROVIDERS = ["google", "kakao"]

# 앱 시작/종료 이벤트 강화
@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작시 초기화"""
    logger.info("🚀 Food Analyzer API 시작 중...")
    
    try:
        # 환경 변수 확인
        required_vars = ["JWT_SECRET_KEY", "DATABASE_URL"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            logger.error(f"❌ 필수 환경 변수 누락: {missing_vars}")
            logger.error("❌ 애플리케이션을 시작할 수 없습니다.")
            raise RuntimeError(f"필수 환경 변수가 설정되지 않았습니다: {missing_vars}")
        
        logger.info("✅ 필수 환경 변수 확인 완료")
        
        # 데이터베이스 초기화
        create_db_and_tables()
        logger.info("✅ 데이터베이스 초기화 완료")
        
        # 기본 역할 자동 생성
        from sqlmodel import Session
        from database.models import Role
        with Session(engine) as session:
            user_role = session.exec(
                select(Role).where(Role.name == "user")
            ).first()
            if not user_role:
                session.add(Role(name="user", description="일반 사용자"))
                session.commit()
                logger.info("✅ 기본 역할 'user' 생성 완료")
                
        # AI 서비스 초기화
        if not initialize_services():
            raise RuntimeError("AI 서비스 초기화 실패")
        logger.info("✅ AI 서비스 초기화 완료")
        
        # OAuth 설정 확인
        oauth_vars = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "KAKAO_REST_API_KEY", "KAKAO_CLIENT_SECRET"]
        oauth_configured = any(os.getenv(var) for var in oauth_vars)
        
        if oauth_configured:
            logger.info("✅ OAuth 설정 확인됨")
        else:
            logger.warning("⚠️ OAuth 설정이 확인되지 않습니다. 소셜 로그인 기능을 사용할 수 없습니다.")
        
        # 필수 환경 변수 재확인
        critical_vars = ["JWT_SECRET_KEY", "DATABASE_URL"]
        missing_critical = [var for var in critical_vars if not os.getenv(var)]
        if missing_critical:
            logger.error(f"❌ 필수 환경 변수 누락: {missing_critical}")
            raise RuntimeError(f"필수 환경 변수가 설정되지 않았습니다: {missing_critical}")
        
        logger.info("🎉 애플리케이션 준비 완료!")
        
        # 환경에 따라 동적 URL 출력
        app_env = os.getenv('APP_ENV', 'local')
        if app_env == 'local':
            host = os.getenv('HOST', '127.0.0.1')
            port = int(os.getenv('PORT', 8000))
            base_url = f"http://{host}:{port}"
            logger.info(f"🏠 로컬 환경에서 실행 중: {base_url}")
        else: # cloud
            host = os.getenv('HOST', '0.0.0.0')
            port = int(os.getenv('PORT', 8080))
            # 클라우드 환경에서는 실제 외부 URL을 알 수 없으므로, 접속 정보를 안내합니다.
            base_url = f"http://{host}:{port}"
            logger.info(f"☁️ 클라우드 환경에서 실행 중. 포트 {port}에서 수신 대기합니다.")
            logger.info("   외부에서는 클라우드 플랫폼이 제공하는 Public URL로 접속하세요.")

        logger.info(f"📍 API 문서 (Swagger): {base_url}/docs")
        logger.info(f"📍 API 문서 (ReDoc)  : {base_url}/redoc")
        logger.info(f"📍 헬스체크         : {base_url}/health")
        
    except Exception as e:
        logger.error(f"❌ 시작 오류: {e}", exc_info=True)
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료시 정리 작업"""
    logger.info("📴 애플리케이션 종료 중...")

# === API 엔드포인트들 ===

@app.get("/", response_model=BaseResponse)
def read_root():
    """API 루트 엔드포인트"""
    logger.info("📍 루트 엔드포인트 호출")
    return BaseResponse(
        message="Food Ingredient Analysis API v2.0 - 정상 작동 중",
        success=True
    )

@app.get("/health")
def health_check():
    """상세 헬스체크"""
    logger.info("🏥 헬스체크 호출")
    
    try:
        # 데이터베이스 연결 테스트
        from database.database import test_connection
        db_status = "connected" if test_connection() else "disconnected"
    except Exception as e:
        logger.error(f"데이터베이스 연결 테스트 실패: {e}")
        db_status = "error"
    
    # 환경 변수 상태 확인
    env_status = {
        "database": "configured" if os.getenv("DATABASE_URL") else "missing",
        "jwt": "configured" if os.getenv("JWT_SECRET_KEY") else "missing",
        "google_oauth": "configured" if os.getenv("GOOGLE_CLIENT_ID") else "missing",
        "kakao_oauth": "configured" if os.getenv("KAKAO_REST_API_KEY") else "missing"
    }
    
    # 전체 상태 결정
    overall_status = "healthy"
    if db_status == "disconnected" or db_status == "error":
        overall_status = "degraded"
    if not os.getenv("JWT_SECRET_KEY") or not os.getenv("DATABASE_URL"):
        overall_status = "unhealthy"
    
    return {
        "status": overall_status,
        "service": "food-analyzer-api",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
        "database": {
            "connection": db_status,
            "url_configured": bool(os.getenv("DATABASE_URL"))
        },
        "environment": env_status,
        "features": {
            "ocr_analysis": "available",
            "ai_chatbot": "available", 
            "user_logs": "available",
            "rag_system": "enabled",
            "social_auth": "available" if any(status == "configured" for status in env_status.values()) else "unavailable"
        }
    }

# OAuth 디버깅 전용 엔드포인트 추가
@app.get("/debug/oauth/status")
def oauth_debug_status():
    """OAuth 설정 상태 확인 (디버깅용)"""
    logger.info("🔍 OAuth 디버깅 상태 확인")
    
    return {
        "oauth_providers": {
            "google": {
                "client_id": "configured" if os.getenv("GOOGLE_CLIENT_ID") else "missing",
                "client_secret": "configured" if os.getenv("GOOGLE_CLIENT_SECRET") else "missing",
                "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI", "not_set")
            },
            "kakao": {
                "client_id": "configured" if os.getenv("KAKAO_REST_API_KEY") else "missing", 
                "client_secret": "configured" if os.getenv("KAKAO_CLIENT_SECRET") else "missing",
                "redirect_uri": os.getenv("KAKAO_REDIRECT_URI", "not_set")
            }
        },
        "session_config": {
            "secret_key": "configured" if SESSION_SECRET_KEY else "missing",
            "cookie_name": "food_analyzer_session"
        },
        "jwt_config": {
            "secret_key": "configured" if os.getenv("JWT_SECRET_KEY") else "missing",
            "algorithm": JWT_ALGORITHM
        },
        "streamlit_app_url": os.getenv("STREAMLIT_APP_URL", "not_set")
    }

@app.post("/analyze/ocr/", response_model=OcrResponse)
async def analyze_image_ocr(
    file: UploadFile = File(..., description="분석할 성분표 이미지 파일"),
    user_id: str = Header(None, alias="X-User-Id", description="사용자 ID (이미지 저장용)")
):
    """
    이미지 업로드 후 OCR을 통한 성분 추출
    
    - **file**: 이미지 파일 (JPG, PNG, WEBP 등)
    - **X-User-Id**: 사용자 ID (이미지 저장용, 선택사항)
    - **최대 크기**: 10MB
    - **반환**: 추출된 성분 목록과 처리 시간
    """
    # 파일 타입 검증
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(
            status_code=400,
            detail="이미지 파일만 업로드 가능합니다"
        )
    
    # 파일 크기 검증
    file_bytes = await file.read()
    if len(file_bytes) > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(
            status_code=400,
            detail="파일 크기는 10MB를 초과할 수 없습니다"
        )
    
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=400,
            detail="빈 파일입니다"
        )
    
    return await perform_ocr_analysis(file_bytes, file.filename, user_id)

@app.post("/analyze/chatbot/", response_model=AnalysisResponse)
async def analyze_ingredients_chatbot(
    request: AnalysisRequest,
    user_id: str = Depends(validate_user_id),
    session: Session = Depends(get_session)
):
    """
    추출된 성분 목록으로 AI 챗봇 분석 및 섭취 가이드 제공
    
    - **ingredients**: 분석할 성분 목록
    - **user_id**: 사용자 ID (헤더)
    - **반환**: AI 분석 결과 및 저장된 기록 ID
    """
    # 사용자 ID 일치 확인
    if user_id != request.user_id:
        raise HTTPException(
            status_code=403,
            detail="사용자 인증 정보 불일치"
        )
    
    # 성분 목록 검증
    if not request.ingredients or len(request.ingredients) == 0:
        raise HTTPException(
            status_code=400,
            detail="분석할 성분이 없습니다"
        )
    
    return perform_chatbot_analysis_and_save(
        ingredients=request.ingredients,
        user_id=request.user_id,
        session=session,
        image_url=request.image_url,
        ocr_result=request.ocr_result
    )

@app.get("/users/{user_id}/logs/", response_model=UserFoodLogsResponse)
def get_user_food_logs(
    user_id: str,
    limit: int = Query(default=20, ge=1, le=100, description="조회할 기록 수"),
    offset: int = Query(default=0, ge=0, description="건너뛸 기록 수"),
    session: Session = Depends(get_session),
    # 👈 헤더에서 가져온 유저 ID를 current_user로 받음
    current_user_from_header: str = Depends(validate_user_id)
):
    """
    특정 사용자의 음식 분석 기록 조회
    
    - **user_id**: 조회할 사용자 ID
    - **limit**: 한 번에 가져올 기록 수 (1-100)
    - **offset**: 건너뛸 기록 수 (페이징용)
    - **반환**: 사용자의 분석 기록 목록
    """
    # 권한 확인 (자신의 기록만 조회 가능)
    if current_user_from_header != user_id:
        raise HTTPException(
            status_code=403,
            detail="다른 사용자의 기록은 조회할 수 없습니다"
        )
    
    # 기록 조회 쿼리
    query = (
        select(UserFoodLog)
        .where(UserFoodLog.user_id == user_id)
        .order_by(UserFoodLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    
    logs = session.exec(query).all()
    
    if not logs and offset == 0:
        raise HTTPException(
            status_code=404,
            detail="분석 기록을 찾을 수 없습니다"
        )
    
    # 응답 데이터 변환
    log_responses = [
        FoodLogResponse(
            id=log.id,
            image_url=log.image_url,
            ocr_result=log.ocr_result,
            gemini_response=log.gemini_response,
            created_at=log.created_at
        ) for log in logs
    ]
    
    return UserFoodLogsResponse(
        logs=log_responses,
        message=f"{len(log_responses)}개의 기록을 조회했습니다"
    )

@app.get("/users/{user_id}/logs/{log_id}/", response_model=FoodLogResponse)
def get_single_food_log(
    user_id: str,
    log_id: UUID,
    session: Session = Depends(get_session),
    # 👈 헤더에서 가져온 유저 ID를 current_user로 받음
    current_user_from_header: str = Depends(validate_user_id)
):
    """
    특정 분석 기록 상세 조회
    
    - **user_id**: 사용자 ID
    - **log_id**: 조회할 기록 ID
    - **반환**: 상세 분석 기록
    """
    # 권한 확인
    if current_user_from_header != user_id:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다")
    
    # 기록 조회
    log = session.get(UserFoodLog, log_id)
    if not log or log.user_id != user_id:
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다")
    
    return FoodLogResponse(
        id=log.id,
        image_url=log.image_url,
        ocr_result=log.ocr_result,
        gemini_response=log.gemini_response,
        created_at=log.created_at
    )

@app.delete("/users/{user_id}/logs/{log_id}/", response_model=BaseResponse)
def delete_user_food_log(
    user_id: str,
    log_id: UUID,
    session: Session = Depends(get_session),
    # 👈 헤더에서 가져온 유저 ID를 current_user로 받음
    current_user_from_header: str = Depends(validate_user_id)
):
    """
    특정 사용자의 음식 분석 기록 삭제
    
    - **user_id**: 사용자 ID
    - **log_id**: 삭제할 기록 ID
    - **반환**: 삭제 성공 메시지
    """
    # 권한 확인
    if current_user_from_header != user_id:
        raise HTTPException(status_code=403, detail="삭제 권한이 없습니다")
    
    # 기록 조회 및 소유자 확인
    log = session.get(UserFoodLog, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="삭제할 기록을 찾을 수 없습니다")
    
    if log.user_id != user_id:
        raise HTTPException(status_code=403, detail="다른 사용자의 기록은 삭제할 수 없습니다")
    
    # 기록 삭제
    session.delete(log)
    session.commit()
    
    # 이미지 파일 삭제
    if log.image_url:
        try:
            delete_image(log.image_url)
            logger.info(f"Image file {log.image_url} deleted successfully.")
        except Exception as e:
            logger.error(f"Failed to delete image file {log.image_url}: {e}")
    
    return BaseResponse(message="기록이 성공적으로 삭제되었습니다")

@app.delete("/users/{user_id}/logs/", response_model=BaseResponse)
def delete_all_user_logs(
    user_id: str,
    session: Session = Depends(get_session),
    # 👈 헤더에서 가져온 유저 ID를 current_user로 받음
    current_user_from_header: str = Depends(validate_user_id)
):
    """
    사용자의 모든 분석 기록 삭제
    
    - **user_id**: 사용자 ID
    - **반환**: 삭제 완료 메시지
    """
    # 권한 확인
    if current_user_from_header != user_id:
        raise HTTPException(status_code=403, detail="삭제 권한이 없습니다")
    
    # 모든 기록 조회 및 삭제
    logs = session.exec(
        select(UserFoodLog).where(UserFoodLog.user_id == user_id)
    ).all()
    
    if not logs:
        raise HTTPException(status_code=404, detail="삭제할 기록이 없습니다")
    
    deleted_count = len(logs)
    for log in logs:
        session.delete(log)
    
    session.commit()
    
    # 모든 이미지 파일 삭제
    for log in logs:
        if log.image_url:
            try:
                delete_image(log.image_url)
                logger.info(f"Image file {log.image_url} deleted successfully.")
            except Exception as e:
                logger.error(f"Failed to delete image file {log.image_url}: {e}")
    
    return BaseResponse(message=f"{deleted_count}개의 기록이 모두 삭제되었습니다")

# 개발용 엔드포인트 (배포시 제거 권장)
@app.get("/debug/logs/count/")
def get_total_logs_count(session: Session = Depends(get_session)):
    """전체 기록 수 조회 (디버그용)"""
    count = len(session.exec(select(UserFoodLog)).all())
    return {"total_logs": count}

@app.get("/debug/environment/")
def get_environment_info():
    """환경 변수 및 설정 정보 조회 (디버그용)"""
    return {
        "database_url": os.getenv("DATABASE_URL", "not_set"),
        "google_client_id": os.getenv("GOOGLE_CLIENT_ID", "not_set")[:10] + "..." if os.getenv("GOOGLE_CLIENT_ID") else "not_set",
        "kakao_client_id": os.getenv("KAKAO_REST_API_KEY", "not_set")[:10] + "..." if os.getenv("KAKAO_REST_API_KEY") else "not_set",
        "streamlit_app_url": os.getenv("STREAMLIT_APP_URL", "not_set"),
        "jwt_secret_key": "set" if os.getenv("JWT_SECRET_KEY") else "not_set",
        "log_level": os.getenv("LOG_LEVEL", "not_set"),
        "python_unbuffered": os.getenv("PYTHONUNBUFFERED", "not_set")
    }

@app.get("/debug/oauth/")
def get_oauth_config():
    """OAuth 설정 정보 조회 (디버그용)"""
    return {
        "google_redirect_uri": os.getenv("GOOGLE_REDIRECT_URI", "not_set"),
        "kakao_redirect_uri": os.getenv("KAKAO_REDIRECT_URI", "not_set"),
        "supported_providers": list(SUPPORTED_PROVIDERS)
    }

if __name__ == "__main__":
    import uvicorn
    
    # 환경에 따라 호스트 및 포트 설정
    app_env = os.getenv('APP_ENV', 'local')
    
    if app_env == 'local':
        host = os.getenv('HOST', '127.0.0.1')
        port = int(os.getenv('PORT', 8000))
        reload = True
    else: # cloud
        host = os.getenv('HOST', '0.0.0.0')
        # Google Cloud Run 같은 서비스는 PORT 환경변수로 포트를 지정
        port = int(os.getenv('PORT', 8080))
        reload = False

    uvicorn.run(
        "main:app", 
        host=host, 
        port=port,
        log_level="info",
        reload=reload
    )
