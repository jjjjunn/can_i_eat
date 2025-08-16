from fastapi import Request, Depends, HTTPException, APIRouter, BackgroundTasks
from fastapi.responses import RedirectResponse
from sqlmodel import SQLModel, Field, Relationship, Session as SQLSession, select
from sqlalchemy.orm import Session
from database.models import User, Role
from database.database import get_db
import logging
from oauth.unlink_services import social_unlink_task
import os

router = APIRouter()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STREAMLIT_APP_URL = os.getenv("STREAMLIT_APP_URL")

# 로그아웃
@router.post("/logout")
async def logout(request: Request):
    request.session.pop("username", None)
    return {"message": "로그아웃 완료!"}

def create_or_update_social_user(db: Session, user_info: dict, provider: str, request: Request, access_token: str):
    """
    제공된 사용자 정보로 DB에서 사용자를 찾거나,
    새로운 사용자를 생성/업데이트하고 세션에 저장합니다.
    """
    logger.info(f"소셜 로그인 처리 시작: 제공자 {provider}, 사용자 정보 {user_info}")

    # 소셜 ID는 각 제공자 API 응답에서 직접 가져옵니다.
    social_id_value = user_info.get('provider_id')
    user_email = user_info.get('email')
    user_name = user_info.get('name')

    if not all([user_email, social_id_value, user_name]):
        logger.error("필수 사용자 정보가 누락되었습니다.")
        raise HTTPException(status_code=400, detail="필수 사용자 정보가 제공되지 않았습니다.")
    
    # 기존 사용자 조회: provider와 provider_id로 유니크하게 식별
    user = db.execute(
        select(User).where(
            User.provider == provider,
            User.provider_id == social_id_value
        )
    ).scalars().first()
    
    if not user:
        # 신규 사용자 생성
        user_role = db.execute(select(Role).where(Role.name == "user")).scalars().first()
        
        if not user_role:
            logger.error("기본 역할 'user'가 데이터베이스에 존재하지 않습니다.")
            raise HTTPException(status_code=500, detail="기본 사용자 역할을 찾을 수 없습니다.")

        try:
            role_id = user_role.id
        except AttributeError:
            # 만약 .id 접근이 안 되면 딕셔너리 형태로 접근
            role_id = getattr(user_role, 'id', None)
            if role_id is None:
                # 최후의 수단: 직접 쿼리로 role_id 가져오기
                role_query_result = db.execute(select(Role.id).where(Role.name == "user")).first()
                role_id = role_query_result
        
        if role_id is None:
            logger.error("'user' 역할의 ID를 가져올 수 없습니다.")
            raise HTTPException(status_code=500, detail="기본 사용자 역할 ID를 찾을 수 없습니다.")

        user = User(
            id=social_id_value,  # 소셜 로그인 ID를 사용자 ID로 사용
            name=user_name,
            email=user_email,
            provider=provider,
            provider_id=social_id_value,
            role_id=role_id
        )
        db.add(user)
        logger.info(f"신규 사용자 생성: {user_email} (소셜 ID: {social_id_value})")
    else:
        # 기존 사용자 정보 업데이트
        user.name = user_name
        user.email = user_email
        logger.info(f"기존 사용자 업데이트: {user.email} (소셜 ID: {social_id_value})")

    try:
        db.commit()
        db.refresh(user)
        logger.info(f"사용자 정보 저장 성공: {user.email}, ID: {user.id}")
    except Exception as e:
        db.rollback()
        logger.error(f"사용자 정보 저장 실패: {e}")
        raise HTTPException(status_code=500, detail="사용자 정보를 저장하는 중 오류가 발생했습니다.")

    # 사용자 정보 저장 후 세션에 사용자 정보 저장
    request.session['id'] = str(user.id)
    request.session['name'] = user.name
    request.session['provider_id'] = social_id_value
    request.session['provider'] = provider
    request.session['access_token'] = access_token
    request.session['is_logged_in'] = True  # 로그인 상태 플래그 추가

    # 사용자 객체 반환
    return user

# 더 안전한 Role 조회 함수 (추가 제안)
def get_user_role_id(db: Session) -> int:
    """
    'user' 역할의 ID를 안전하게 가져오는 함수
    """
    try:
        # 방법 1: 전체 객체 조회 후 ID 접근
        role = db.execute(select(Role).where(Role.name == "user")).first()
        if role and hasattr(role, 'id'):
            return role.id
        
        # 방법 2: ID만 직접 조회
        role_id = db.execute(select(Role.id).where(Role.name == "user")).first()
        if role_id:
            return role_id
            
        # 방법 3: 없으면 생성
        new_role = Role(name="user", description="일반 사용자")
        db.add(new_role)
        db.commit()
        db.refresh(new_role)
        logger.info("'user' 역할이 자동으로 생성되었습니다.")
        return new_role.id
        
    except Exception as e:
        logger.error(f"역할 조회/생성 중 오류: {e}")
        raise HTTPException(status_code=500, detail="사용자 역할 처리 중 오류가 발생했습니다.")


# 회원 탈퇴
@router.delete("/users/{id}")
async def delete_user(request: Request, id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    logger.info(f"회원 탈퇴 요청: 사용자 ID {id}")

    user_id = request.session.get("id") # 사용자 ID
    social_id = request.session.get("social_id") # 소셜 ID
    provider = request.session.get("provider") # 로그인 제공자 정보

    if user_id is None and (social_id is None or provider is None):
        logger.warning("세션에 사용자 ID 또는 소셜 ID가 없음.")
        raise HTTPException(status_code=401, detail="Not Authorized")

    # 사용자를 user_id 또는 social_id로 조회
    user_query = db.query(User)

    if user_id is not None:
        user_query = user_query.filter(User.id == user_id)

    if social_id is not None:
        if provider == "google":
            user_query = user_query.filter(User.google_id == social_id)
        elif provider == "kakao":
            user_query = user_query.filter(User.kakao_id == social_id)
        elif provider == "naver":
            user_query = user_query.filter(User.naver_id == social_id)
        else:
            logger.warning("지원하지 않는 소셜 로그인 제공자입니다.")
            raise HTTPException(status_code=403, detail="Unsupported Social Provider")

    user = user_query.first()

    if user is None:
        logger.error(f"사용자 찾기 실패: ID {user_id} 또는 {social_id}에 대한 사용자가 존재하지 않음.")
        raise HTTPException(status_code=404, detail="User를 찾을 수 없습니다.")

    # # 사용자가 작성한 모든 메모 삭제
    # memos = db.query(Memo).filter(Memo.user_id == user_id).all()
    # logger.info(f"{len(memos)}개의 메모를 삭제합니다.")
    # for memo in memos:
    #     db.delete(memo)

    # 사용자 정보 삭제
    db.delete(user)

    try:
        db.commit()
        
        # 소셜 로그인 연동 해제
        access_token = request.session.get("access_token")
        if access_token and provider:
            background_tasks.add_task(social_unlink_task, provider, access_token)
        logger.info(f"사용자 ID {user_id}가 성공적으로 삭제되었습니다.")

    except Exception as e:
        db.rollback()
        logger.error(f"회원 탈퇴 오류: {e}")  # 에러 내용 출력
        raise HTTPException(status_code=500, detail="회원 탈퇴에 실패하였습니다. 다시 시도해 주세요.")

    # 세션 비우기
    request.session.clear()

    # 탈퇴 성공 응답 리턴
    return {"success": True, "message": "회원 탈퇴가 완료되었습니다."}
