import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import json
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv
import logging
from streamlit_cookies_manager import EncryptedCookieManager

# 공통 함수 import
from utils.utils import verify_jwt_token, initialize_app
from utils.logs import UserLogsViewer, format_datetime, display_log_detail

# .env 파일에서 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 설정 및 전역 변수 ---
API_BASE_URL = os.getenv("API_URL")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# --- 세션 상태 키 미리 초기화 ---
for key, default in [
    ("logged_in", False),
    ("jwt_token", None),
    ("username", None),
    ("user_id", None),
    ("logs_viewer", None),
    ("current_page", 0),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# 현재 페이지 설정 - 숫자로 설정
if "current_page" not in st.session_state:
    st.session_state["current_page"] = 0

if st.session_state.get("logged_in", False):
    # st.write("로그인됨, 토큰:", "***" + st.session_state["jwt_token"][-10:] if st.session_state["jwt_token"] else "None")
    st.write("로그인됨")
else:
    st.warning("로그인 필요")

cookies = EncryptedCookieManager(
    prefix="can_i_eat",
    password=os.getenv('EncryptedCookieManager_PW')
    )
    

if not cookies.ready():
    st.stop()

# --- UI 헬퍼 함수 ---
def format_datetime(dt_str: str) -> str:
    """ISO 형식의 날짜를 읽기 쉬운 형식으로 변환"""
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return dt_str

def display_log_detail(log: Dict[str, Any]) -> Optional[str]:
    """개별 로그의 상세 정보 표시"""
    with st.expander(f"📝 기록 ID: {log['id']}", expanded=False):
        col1, col2 = st.columns([1, 2])
        
        with col1:
            image_url = log.get('image_url')
            if image_url:
                # 상대 경로일 경우, API_BASE_URL을 붙여 완전한 URL 생성
                if image_url.startswith('/'):
                    full_image_url = f"{API_BASE_URL.rstrip('/')}{image_url}"
                else:
                    full_image_url = image_url
                
                st.image(full_image_url, caption="업로드된 이미지", width=300)
            else:
                st.info("이미지가 없습니다")
        
        with col2:
            st.write("**생성 시간:**", format_datetime(log['created_at']))
            
            if log.get('ocr_result'):
                st.write("**OCR 결과:**")
                st.text_area("OCR 결과 내용", value=log['ocr_result'], height=100, key=f"ocr_{log['id']}")
            
            if log.get('gemini_response'):
                st.write("**AI 분석 결과:**")
                try:
                    if isinstance(log['gemini_response'], str):
                        gemini_data = json.loads(log['gemini_response'])
                        st.json(gemini_data)
                    else:
                        st.json(log['gemini_response'])
                except:
                    st.text_area("AI 분석 결과 내용", value=str(log['gemini_response']), height=150, key=f"gemini_{log['id']}")
        
        # 삭제 버튼
        if st.button(f"🗑️ 이 기록 삭제", key=f"delete_{log['id']}", type="secondary"):
            return log['id']
    
    return None

# --- Streamlit 앱 메인 함수 ---
def main():
    st.set_page_config(
        page_title="내 음식 분석 기록",
        page_icon="🍽️",
        layout="wide"
    )
    
    initialize_app()

    # # 초기 세션 상태
    # if "logged_in" not in st.session_state:
    #     st.session_state.logged_in = False
    #     st.session_state.jwt_token = None
    #     st.session_state.username = None
    #     st.session_state.user_id = None
    
    # --- 로그인 상태 확인 및 토큰 처리 ---
    jwt_token = st.query_params.get("token") or cookies.get("jwt_token")
    logger.info(f"URL 토큰 값: {st.query_params.get('token')}")
    logger.info(f"쿠키 토큰 값: {cookies.get('jwt_token')}")
    logger.info(f"선택된 토큰 값: {jwt_token}")

    # 토큰 검증 및 세션 저장
    if jwt_token:
        payload = verify_jwt_token(jwt_token)
        logger.info(f"토큰 페이로드: {payload}")
        if payload:
            st.session_state.logged_in = True
            st.session_state.jwt_token = jwt_token
            st.session_state.username = payload.get("nickname", "사용자")
            st.session_state.user_id = payload.get("sub")  # JWT의 sub 필드가 사용자 ID
            cookies["jwt_token"] = jwt_token  # 쿠키 저장
            cookies.save()
            st.write(f"안녕하세요, {st.session_state.username}님!")
        else:
            st.error("토큰 검증 실패")

    # 로그인 상태 아니면 로그인 안내
    if not st.session_state.logged_in:
        st.title("🍽️ 로그인하여 기록을 확인하세요")
        st.markdown("---")
        st.warning("로그인이 필요합니다. URL에 유효한 JWT 토큰을 포함하여 접근해주세요.")
        st.stop()
        
    # logs_viewer가 None이면 새로 생성
    if 'logs_viewer' not in st.session_state or st.session_state.logs_viewer is None:
        st.session_state.logs_viewer = UserLogsViewer(API_BASE_URL)

    # --- 페이지 메인 컨텐츠 ---
    st.title(f"🍽️ {st.session_state['username']}님의 음식 분석 기록")
    st.markdown("---")

    # 초기화
    if 'logs_viewer' not in st.session_state:
        st.session_state.logs_viewer = UserLogsViewer(API_BASE_URL)
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 0

    # --- 사이드바 ---
    with st.sidebar:
        st.header("🔧 설정")
        st.metric("현재 로그인 사용자", st.session_state.get('username', '알 수 없음'))
        page_size = st.slider("한 페이지당 기록 수", min_value=1, max_value=50, value=10)

        if st.button("🔄 기록 새로고침", type="primary"):
            st.session_state.current_page = 0
            st.rerun()

        if st.button("🚪 로그아웃", type="secondary"):
            # 세션 상태 초기화
            st.session_state.logged_in = False
            st.session_state.jwt_token = None
            st.session_state.username = None
            st.session_state.user_id = None
            st.session_state.logs_viewer = None
            st.session_state.current_page = 0
            cookies["jwt_token"] = ""
            cookies.save()
            st.rerun()

    # 기록 조회
    user_id = st.session_state['user_id']
    auth_token = st.session_state['jwt_token']
    offset = st.session_state.current_page * page_size

    logger.info(f"기록 조회 요청: user_id={user_id}, offset={offset}, limit={page_size}")

    result = st.session_state.logs_viewer.get_user_logs(
        user_id=user_id,
        limit=page_size,
        offset=offset,
        auth_token=auth_token
    )

    if 'error' in result:
        st.error(f"오류 발생: {result['error']}")
        if result.get('status_code') == 404:
            st.info("조회할 기록이 없습니다.")
        return

    logs = result.get('logs', [])
    message = result.get('message', '')

    if not logs:
        st.info("아직 분석한 기록이 없습니다. 먼저 음식을 분석해보세요!")
        return

    # 헤더 정보
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.success(message)
    with col2:
        st.metric("현재 페이지", st.session_state.current_page + 1)
    with col3:
        st.metric("표시 기록 수", len(logs))

    # 전체 삭제 버튼
    if st.button("🗑️ 모든 기록 삭제", type="secondary", help="이 사용자의 모든 기록을 삭제합니다"):
        with st.spinner("모든 기록을 삭제하는 중..."):
            delete_result = st.session_state.logs_viewer.delete_all_logs(user_id, auth_token)
            if 'error' in delete_result:
                st.error(f"삭제 실패: {delete_result['error']}")
            else:
                st.success(delete_result.get('message', '모든 기록이 삭제되었습니다'))
                st.rerun()

    st.markdown("---")

    delete_log_id = None
    for log in logs:
        log_to_delete = display_log_detail(log)
        if log_to_delete:
            delete_log_id = log_to_delete

    if delete_log_id:
        with st.spinner("기록을 삭제하는 중..."):
            delete_result = st.session_state.logs_viewer.delete_log(user_id, delete_log_id, auth_token)
            if 'error' in delete_result:
                st.error(f"삭제 실패: {delete_result['error']}")
            else:
                st.success(delete_result.get('message', '기록이 삭제되었습니다'))
                st.rerun()

    st.markdown("---")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("⬅️ 이전 페이지") and st.session_state.current_page > 0:
            st.session_state.current_page -= 1
            st.rerun()

    with col2:
        st.write(f"페이지: {st.session_state.current_page + 1}")

    with col3:
        if st.button("다음 페이지 ➡️") and len(logs) == page_size:
            st.session_state.current_page += 1
            st.rerun()

    with st.expander("📊 기록 요약 (테이블 형태)", expanded=False):
        if logs:
            df_data = []
            for log in logs:
                df_data.append({
                    "ID": log['id'],
                    "생성시간": format_datetime(log['created_at']),
                    "이미지": "있음" if log.get('image_url') else "없음",
                    "OCR": "있음" if log.get('ocr_result') else "없음",
                    "AI분석": "있음" if log.get('gemini_response') else "없음"
                })
            df = pd.DataFrame(df_data)
            st.dataframe(df, use_container_width=True)


if __name__ == "__main__":
    main()