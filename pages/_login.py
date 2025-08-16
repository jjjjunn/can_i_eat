import streamlit as st
import requests
import os
import time
import sys
import logging
from urllib.parse import urlencode, quote_plus, urlparse, parse_qs
from typing import Optional

# Streamlit 페이지 설정을 위해 추가
st.set_page_config(
    page_title="로그인",
    page_icon="🔑",
    layout="centered",
)

# pages/ 디렉토리를 인식하도록 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "pages")))

# 로그 설정
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# 환경 변수 로드 (env.yaml 포함)
from dotenv import load_dotenv
import yaml
from pathlib import Path

# .env 파일 로드
load_dotenv()

# env.yaml 파일 로드
env_yaml_path = Path(__file__).parent.parent / "env.yaml"
if env_yaml_path.exists():
    with open(env_yaml_path, 'r', encoding='utf-8') as file:
        env_vars = yaml.safe_load(file)
        for key, value in env_vars.items():
            if key not in os.environ:
                os.environ[key] = str(value)

# --- 환경 변수 설정 ---
# FastAPI 백엔드 API URL
API_URL = os.getenv("API_URL")
# Google OAuth2.0 클라이언트 ID
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
# Kakao REST API 키
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")

if not API_URL:
    st.error("API_URL 환경 변수가 설정되지 않았습니다!")
    logging.error("API_URL 환경 변수가 설정되지 않았습니다!")
    st.stop()

# --- 세션 상태 초기화 ---
# `_login.py`는 유저가 로그인하기 전까지의 첫 페이지 역할.
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "user_id" not in st.session_state:
    st.session_state["user_id"] = None
if "username" not in st.session_state:
    st.session_state["username"] = None

# --- OAuth2.0 URL 생성 함수 ---
def create_google_auth_url():
    """Google OAuth2.0 인증 URL을 생성."""
    # 리디렉션 URI는 FastAPI 서버의 콜백 엔드포인트.
    redirect_uri = os.getenv('GOOGLE_REDIRECT_URI')
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid profile email",
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

def create_kakao_auth_url():
    """Kakao OAuth2.0 인증 URL을 생성."""
    # 리디렉션 URI는 FastAPI 서버의 콜백 엔드포인트.
    redirect_uri = os.getenv('KAKAO_REDIRECT_URI')
    params = {
        "client_id": KAKAO_REST_API_KEY,
        "redirect_uri": redirect_uri,
        "response_type": "code",
    }
    return f"https://kauth.kakao.com/oauth/authorize?{urlencode(params)}"

def handle_oauth_callback(token: str, login_status: str):
    """
    FastAPI에서 리디렉션된 JWT 토큰을 처리합니다.
    """
    if login_status == "success" and token:
        try:
            # JWT 토큰을 디코딩하여 사용자 정보 추출
            import jwt
            from utils.utils import JWT_SECRET_KEY, JWT_ALGORITHM
            
            decoded_token = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            
            st.session_state["logged_in"] = True
            st.session_state["user_id"] = decoded_token.get("sub")
            st.session_state["username"] = decoded_token.get("nickname", "Guest")
            st.session_state["jwt_token"] = token
            
            st.success(f"✅ 로그인 성공! 환영합니다, {st.session_state['username']}님.")
            st.balloons()
            logging.info(f"로그인 성공: {st.session_state['username']}, ID: {st.session_state['user_id']}")
            
            # URL의 쿼리 파라미터 제거
            st.query_params.clear()
            
            # 페이지 이동
            st.switch_page("/app")
        except Exception as e:
            st.error(f"❌ 토큰 처리 실패: {e}")
            logging.error(f"토큰 처리 실패: {e}")
    else:
        st.error("❌ 로그인 실패")
        logging.error("로그인 실패")

def main():
    """메인 로그인 페이지 UI를 렌더링합니다."""
    # 이미 로그인된 경우
    if st.session_state.get("logged_in", False):
        st.info("이미 로그인되어 있습니다. 👈 왼쪽 사이드바에서 원하는 메뉴를 선택해주세요.")
        logging.info(f"이미 로그인된 사용자: {st.session_state.get('username')}")
        time.sleep(1)
        st.stop()

    st.title("🔑 소셜 로그인")
    st.markdown("👋 소셜 로그인으로 한 번에 시작하기.")
    st.subheader("🔍 먹어도 돼? (임신부를 위한 성분 분석기) ")

    # 쿼리 파라미터에서 JWT 토큰과 로그인 상태 추출
    query_params = st.query_params
    token = query_params.get("token")
    login_status = query_params.get("login")
    
    # FastAPI에서 리디렉션된 JWT 토큰 처리
    if token and login_status:
        handle_oauth_callback(token, login_status)
        st.stop()

    # 로그인 버튼 UI
    st.write("---")
    
    # Google 로그인 버튼
    google_url = create_google_auth_url()
    st.markdown(
        f'<a href="{google_url}" target="_self" style="text-decoration: none;">'
        '<button style="width: 100%; padding: 15px; font-size: 18px; border-radius: 5px; border: 1px solid #ccc; background-color: white; cursor: pointer;">'
        '<span><img src="https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png" height="24" style="vertical-align: middle; margin-right: 10px;"></span>'
        '<span style="vertical-align: middle;">Google로 계속하기</span>'
        '</button></a>',
        unsafe_allow_html=True
    )
    
    st.write("") # 버튼 사이 간격
    
    # Kakao 로그인 버튼
    kakao_url = create_kakao_auth_url()
    st.markdown(
        f'<a href="{kakao_url}" target="_self" style="text-decoration: none;">'
        '<button style="width: 100%; padding: 15px; font-size: 18px; border-radius: 5px; border: 1px solid #ccc; background-color: #FEE500; cursor: pointer;">'
        # '<img src="https://developers.kakao.com/assets/img/about/logos/kakaolink_btn_small_ov.png" height="24" style="vertical-align: middle; margin-right: 10px;">'
        '<span style="vertical-align: middle; color: #3A1D1D;">카카오로 로그인</span>'
        '</button></a>',
        unsafe_allow_html=True
    )

    st.write("---")

if __name__ == "__main__":
    main()

