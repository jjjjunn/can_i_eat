import streamlit as st
from PIL import Image
import time
import os
import tempfile
import json
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import jwt
import requests

# .env 로드
load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="먹어도 돼?",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# services 모듈 가져오기
from services.ocr_service import VisionTextExtractor
from services.chatbot import IngredientsAnalyzer
from services.rag import OptimizedRAGSystem

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "utils")))

from utils.utils import initialize_app
from utils.app_classes import (
    AnalysisHistoryManager,
    IngredientsDisplayer,
    SessionStateManager,
    ImageProcessor,
    ChatbotAnalyzer
)

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 상수 정의
MAX_IMAGE_SIZE = 2048
MAX_HISTORY_SIZE = 10
SUPPORTED_TYPES = ["jpg", "jpeg", "png", "jfif", "webp"]

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")


def create_sidebar() -> Dict[str, Any]:
    """사이드바 생성 및 설정 관리"""
    with st.sidebar:
        st.markdown("### ⚙️ 설정")
        
        # 설정 옵션들
        settings = {
            'show_progress': st.checkbox("진행률 표시", value=st.session_state.show_progress),
            'auto_clean': st.checkbox("자동 성분 정리", value=st.session_state.auto_clean,
                                    help="의미없는 텍스트 자동 제거"),
            'use_rag': st.checkbox("RAG 기능 사용", value=st.session_state.use_rag,
                                 help="논문 데이터베이스 활용")
        }
        
        # 세션 상태 업데이트
        st.session_state.update(settings)
        st.markdown("---")
        
        # 분석 기록
        AnalysisHistoryManager.display_sidebar_history()
        st.markdown("---")
        
        # 사용 팁
        with st.expander("💡 사용 팁"):
            st.markdown("""
            **이미지 품질**
            - 고해상도, 선명한 이미지
            - 충분한 조명, 정면 촬영
            - 배경과 글자의 명확한 대비
            
            **성분표 형태**
            - "성분:", "원재료명:" 등 명확한 키워드
            - 기울어지지 않은 수평/수직 정렬
            """)
        
        # 로그아웃 구현
        if st.button("🚪 로그아웃"):
            logger.info(f"[Streamlit] 로그아웃 버튼 클릭 - 사용자: {st.session_state.get('username')}")
            for key in ["logged_in", "username"]: # 로그아웃 시 세션 상태를 완전히 초기화
                st.session_state[key] = None
            # st.session_state.clear()
            st.rerun()
        
        return settings

def analyze_image_with_progress(image: Image.Image, uploaded_file, settings: Dict[str, Any]) -> None:
    """이미지 분석 수행 (진행률 표시 포함)"""
    # ✅ 새로운 이미지 분석일 때만 챗봇 리셋
    SessionStateManager.reset_chatbot()
    
    # 진행률 컨트롤 초기화
    progress_bar = None
    status_text = None
    
    if settings['show_progress']:
        progress_bar = st.progress(0, "분석 준비 중...")
        status_text = st.empty()

    def update_progress(value: int, message: str) -> None:
        """진행률 업데이트 함수"""
        if progress_bar:
            progress_bar.progress(value / 100, text=message)
        if status_text:
            status_text.text(f"상태: {message}")
    
    start_time = time.time()
    
    try:
        # FastAPI OCR 엔드포인트 호출 (이미지 저장 포함)
        api_url = os.getenv("API_URL")
        user_id = st.session_state.get("user_id")
        
        if api_url and user_id:
            update_progress(10, "FastAPI 서버에 이미지 전송 중...")
            
            headers = {
                "X-User-Id": str(user_id)
            }
            
            files = {
                "file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)
            }
            
            response = requests.post(
                f"{api_url.rstrip('/')}/analyze/ocr/",
                files=files,
                headers=headers,
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                extracted_list = data.get("extracted_ingredients", [])
                processing_time = data.get("processing_time", 0)
                saved_image_path = data.get("image_path")
                
                # 저장된 이미지 경로를 세션에 저장
                if saved_image_path:
                    st.session_state.current_image_path = saved_image_path
                    logger.info(f"이미지 저장됨: {saved_image_path}")
                
                update_progress(100, "분석 완료!")
                
            else:
                # FastAPI 호출 실패 시 로컬 OCR 사용
                logger.warning(f"FastAPI OCR 호출 실패: {response.status_code}, 로컬 OCR 사용")
                raise Exception("FastAPI 호출 실패")
                
        else:
            # 로컬 OCR 사용 (기존 방식)
            update_progress(20, "로컬 OCR 분석 중...")
            
            # 임시 파일 생성
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_file_path = tmp_file.name

            # OCR 처리
            extractor = VisionTextExtractor(api_endpoint='eu-vision.googleapis.com')
            extracted_list = extractor.extract_ingredients_with_progress(tmp_file_path, update_progress)
            
            # 임시 파일 정리
            if os.path.exists(tmp_file_path):
                os.remove(tmp_file_path)
            
            processing_time = time.time() - start_time
            
            # 로컬 OCR 사용 시에도 이미지 저장 (사용자 ID가 있는 경우)
            user_id = st.session_state.get("user_id")
            if user_id and extracted_list:
                try:
                    from utils.image_storage import save_image
                    saved_image_path = save_image(uploaded_file.getvalue(), uploaded_file.name, user_id)
                    if saved_image_path:
                        st.session_state.current_image_path = saved_image_path
                        logger.info(f"로컬 OCR 사용 시 이미지 저장됨: {saved_image_path}")
                except Exception as e:
                    logger.warning(f"로컬 OCR 사용 시 이미지 저장 실패: {e}")
        
        # 자동 정리
        if settings['auto_clean'] and extracted_list:
            update_progress(95, "성분 목록 정리 중...")
            extractor = VisionTextExtractor()
            extracted_list = extractor.clean_and_filter_ingredients(extracted_list)
        
        # 진행률 정리
        if progress_bar:
            progress_bar.empty()
        if status_text:
            status_text.empty()
            
        # 결과 처리
        if extracted_list:
            st.success(f"✅ {len(extracted_list)}개 성분 추출 완료! ({processing_time:.1f}초)")
            
            # 상태 업데이트
            st.session_state.current_ingredients = extracted_list
            # OCR 결과를 세션에 저장하여 이후 DB 저장시 활용
            st.session_state.current_ocr_result = {
                "extracted_ingredients": extracted_list,
                "processing_time": processing_time,
                "ingredients_count": len(extracted_list),
                "source": "streamlit_client"
            }
            # 재실행에도 결과가 유지되도록 플래그 설정
            st.session_state.image_analysis_complete = True
            AnalysisHistoryManager.save_to_history(uploaded_file.name, len(extracted_list), processing_time)
            
            # 결과 표시
            IngredientsDisplayer.display_complete_analysis(extracted_list, processing_time)
            
            # 챗봇 분석
            st.markdown("---")
            st.subheader("🤖 AI 분석")
            ChatbotAnalyzer.display_analysis_section(extracted_list)
            
        else:
            st.warning("성분을 추출하지 못했습니다.")
            
    except Exception as e:
        # 오류 처리
        if progress_bar:
            progress_bar.empty()
        if status_text:
            status_text.empty()
            
        st.error(f"분석 오류: {e}")
        st.info("💡 이미지 품질을 확인하거나 다른 이미지로 시도해보세요.")
        logger.error(f"이미지 분석 오류: {e}")

# 홈페이지 콘텐츠
def show_home_content():
    """홈페이지 메인 콘텐츠"""
    if not st.session_state.get("logged_in"):
        show_guest_home()
    else:
        show_user_home()

# --- JWT 토큰 검증 및 로그인 처리 ---
def verify_and_login_user():
    """URL의 JWT 토큰을 검증하고, 유효하면 로그인 상태를 업데이트."""
    query_params = st.query_params
    jwt_token = query_params.get("token")
    # query_params = st.query_params
    # jwt_token = query_params.get("token", [None])[0]

    if jwt_token and not st.session_state.get("logged_in"):
        try:
            # 토큰 디코딩
            payload = jwt.decode(jwt_token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            
            # Streamlit 세션 상태 업데이트
            st.session_state["logged_in"] = True
            st.session_state["user_id"] = payload.get("sub")  # JWT의 sub 필드가 사용자 ID
            st.session_state["username"] = payload.get("nickname", "사용자")
            st.session_state["jwt_token"] = jwt_token # JWT 토큰을 세션에 저장

            st.success(f"✅ 로그인 성공! 환영합니다, {st.session_state['username']}님.")
            st.balloons()
            
            # URL에서 토큰 제거
            st.query_params.clear()
            st.rerun()

        except jwt.InvalidTokenError:
            st.error("❌ 유효하지 않은 로그인 토큰입니다.")
        except Exception as e:
            st.error(f"❌ 로그인 처리 중 오류가 발생했습니다: {e}")


def show_guest_home():
    """비로그인 사용자용 홈페이지"""
    st.title("🔍 먹어도 돼? (임신부를 위한 성분 분석기)")
    st.markdown("식품 섭취 가능 여부를 AI 기반으로 알려 드립니다.")
    
    st.info("👈 왼쪽 사이드바에서 로그인 후 모든 기능을 이용하세요!")
             
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### 🌟 주요 기능
        - **정확한 OCR 분석**: Google Vision API 활용
        - **AI 섭취 가이드**: 성분 기반 섭취 여부 안내
        - **편리한 편집**: 추출 결과 수정 가능
        - **다양한 다운로드**: TXT, JSON 형태 지원
        """)
    
    with col2:
        st.markdown("""
        ### 🎯 사용법
        1. 이미지 업로드
        2. 자동 성분 추출
        3. AI 분석 확인
        4. 결과 다운로드
        """)

def show_user_home():
    """로그인 사용자용 메인 기능"""
    st.title("🔍 먹어도 돼? (임신부를 위한 성분 분석기)")
    st.markdown("업로드한 이미지에서 성분을 추출하고 AI로 분석합니다.")

    st.write(f"환영합니다, {st.session_state.get('username', '사용자')}님!")
    
    # 디버그 정보 표시 (개발용)
    with st.expander("🔧 디버그 정보", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.write("**로그인 상태:**", st.session_state.get('logged_in', False))
            st.write("**사용자 ID:**", st.session_state.get('user_id', 'None'))
            st.write("**사용자명:**", st.session_state.get('username', 'None'))
        with col2:
            st.write("**JWT 토큰:**", "있음" if st.session_state.get('jwt_token') else "없음")
            st.write("**API URL:**", os.getenv("API_URL", "설정되지 않음"))
            st.write("**마지막 저장된 로그 ID:**", st.session_state.get('last_saved_log_id', 'None'))
    
    # 사이드바 설정
    settings = create_sidebar()

    # ✅ 이미지 분석이 완료된 상태인지 확인
    if st.session_state.get('image_analysis_complete', False) and st.session_state.get('current_ingredients'):
        # 분석 완료 후 상태
        st.markdown("### 📋 분석 결과")
        IngredientsDisplayer.display_complete_analysis(
            st.session_state.current_ingredients,
            prefix_key="current_"
        )
        
        st.markdown("---")
        st.subheader("🤖 AI 분석")
        ChatbotAnalyzer.display_analysis_section(st.session_state.current_ingredients)
        
        # 새로운 분석 시작 버튼
        st.markdown("---")
        if st.button("🔄 새로운 이미지 분석", type="secondary"):
            # 상태 초기화
            logger.info("[Streamlit] '새로운 이미지 분석' 버튼 클릭 - 세션 상태 초기화")
            st.session_state.image_analysis_complete = False
            st.session_state.current_ingredients = []
            st.session_state.current_ocr_result = None
            SessionStateManager.reset_chatbot()
            st.rerun()
    
    else:
        # 이미지 업로드 및 분석 단계
        st.subheader("📷 이미지 업로드")
        uploaded_file = st.file_uploader(
            "성분표 이미지를 선택하세요",
            type=SUPPORTED_TYPES,
            help=f"지원 형식: {', '.join(f.upper() for f in SUPPORTED_TYPES)}"
        )

        # 파일 업로드 후 처리
        if uploaded_file is not None:
            image = ImageProcessor.process_and_validate(uploaded_file)
            
            if image:
                st.image(image, caption="업로드된 이미지", use_container_width=True)
                st.info(ImageProcessor.get_image_info(uploaded_file, image))
                st.markdown("---")

                # 분석 버튼
                if st.button("🚀 분석 시작", type="primary", use_container_width=True):
                    logger.info("[Streamlit] '분석 시작' 버튼 클릭")
                    analyze_image_with_progress(image, uploaded_file, settings)
                    # st.rerun()  # 분석 완료 후 페이지 새로고침

        else:
            st.info("👆 성분표 이미지를 업로드해주세요")
            
            # 도움말 섹션 (기존과 동일)
            with st.expander("📖 상세 사용법"):
                st.markdown("""
                ### 🎯 최적의 결과를 위한 팁
                
                **이미지 품질**
                - 300 DPI 이상의 고해상도 이미지
                - 선명하고 흐리지 않은 이미지
                - 1MB 이하 권장
                
                **촬영 환경**
                - 충분한 조명
                - 그림자와 반사 최소화
                - 정면 수직 촬영
                
                **문제 해결**
                - 성분 추출 실패 시: 이미지 품질 확인
                - 오인식 발생 시: 자동 정리 기능 활용
                - 느린 처리 시: 이미지 크기 축소
                """)
            
            # 시스템 상태 (기존과 동일)
            with st.expander("🔧 시스템 상태"):
                col1, col2 = st.columns(2)
                
                with col1:
                    if os.environ.get('GOOGLE_API_KEY'):
                        st.success("✅ Google API 연결됨")
                    else:
                        st.error("❌ Google API 미설정")
                
                with col2:
                    rag_ready = st.session_state.get('rag_system') and st.session_state.rag_system.is_initialized()
                    analyzer_ready = st.session_state.get('analyzer') is not None
                    
                    if rag_ready and analyzer_ready:
                        st.success("✅ AI 서비스 준비됨")
                    else:
                        st.warning("⚠️ AI 서비스 초기화 필요")



def main():
    """메인 애플리케이션"""
    # ✅ 세션 상태 항상 초기화
    SessionStateManager.initialize()
    
    # # 앱 초기화
    initialize_app()
    
    # API URL 확인
    API_URL = os.getenv("API_URL")
    if not API_URL:
        st.error("환경 변수 API_URL이 설정되지 않았습니다!")
        st.stop()

    # 네비게이션 설정
    if st.session_state.get("logged_in"):
        # 로그인한 사용자용 페이지
        pages = [
            st.Page(show_home_content, title="홈", icon="🏠"),
            st.Page("pages/user_logs.py", title="사용자 로그", icon="📈")
        ]
    else:
        # 비로그인 사용자용 페이지
        pages = [
            st.Page(show_home_content, title="홈", icon="🏠"),
            st.Page("pages/_login.py", title="로그인", icon="🔑"),
        ]

    # 네비게이션 실행
    nav = st.navigation(pages)
    nav.run()

    # Footer
    st.markdown("---")
    st.caption("🚀 Powered by Streamlit, Google Gemini & Google Cloud Vision by Recordian")


# 페이지 시작 시 로그인 상태 확인 함수 호출
verify_and_login_user()


# 앱 실행
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"애플리케이션 실행 오류: {e}")
        logger.error(f"앱 실행 오류: {e}", exc_info=True)