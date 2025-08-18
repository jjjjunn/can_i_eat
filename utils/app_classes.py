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
import jwt
import requests

# services 모듈 가져오기
from services.ocr_service import VisionTextExtractor
from services.chatbot import IngredientsAnalyzer
from services.rag import OptimizedRAGSystem

# 환경 변수는 앱 시작점(app.py)에서 중앙 관리 방식으로 로드됩니다.


# 상수 정의
MAX_IMAGE_SIZE = 2048
MAX_HISTORY_SIZE = 10
SUPPORTED_TYPES = ["jpg", "jpeg", "png", "jfif", "webp"]

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SessionStateManager:
    """세션 상태 통합 관리 클래스"""
    
    @staticmethod
    def initialize():
        """세션 상태 초기화 - 모든 기본값을 한 곳에서 관리"""
        defaults = {
            'analysis_history': [],
            'current_ingredients': [],
            'chatbot_analyzed': False,
            'chatbot_result': None,
            'last_analyzed_ingredients_key': '',  # 추가: 마지막 분석된 성분 키
            'rag_system': None,
            'analyzer': None,
            'initialization_complete': False,
            'logged_in': False,
            'use_rag': True,
            'show_progress': True,
            'auto_clean': True,
            
            # ✅ JWT 관련 기본값
            'jwt_token': None,
            'username': None,
            'user_id': None
        }
        
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
                
    @staticmethod
    def reset_chatbot():
        """챗봇 관련 상태만 리셋"""
        st.session_state.chatbot_analyzed = False
        st.session_state.chatbot_result = None
        st.session_state.last_analyzed_ingredients_key = ''  # 키도 초기화
        
    @staticmethod
    def logout():
        """로그아웃 처리"""
        st.session_state.jwt_token = None
        st.session_state.username = None
        st.session_state.user_id = None
        st.session_state.logged_in = False

class ServiceInitializer:
    """AI 서비스 초기화 통합 클래스"""
    
    @staticmethod
    def initialize_all_services() -> bool:
        """모든 AI 서비스를 한 번에 초기화"""
        if (st.session_state.get('rag_system') and 
            st.session_state.get('analyzer')):
            return True
        
        try:
            with st.spinner("AI 서비스 초기화 중..."):
                # RAG 시스템 초기화
                if not st.session_state.get('rag_system'):
                    rag_system = OptimizedRAGSystem()
                    rag_system.initialize()
                    st.session_state.rag_system = rag_system
                
                # 분석기 초기화
                if not st.session_state.get('analyzer'):
                    st.session_state.analyzer = IngredientsAnalyzer()
                
                st.success("AI 서비스 초기화 완료")
                return True
            
        except Exception as e:
            st.error(f"AI 서비스 초기화 실패: {e}")
            logger.error(f"서비스 초기화 오류: {e}")
            return False

class ImageProcessor:
    """이미지 처리 통합 클래스"""
    
    @staticmethod
    def process_and_validate(uploaded_file) -> Optional[Image.Image]:
        """이미지 처리 및 검증을 한 번에 수행"""
        try:
            image = Image.open(uploaded_file)
            
            # 이미지 크기 최적화
            if max(image.size) > MAX_IMAGE_SIZE:
                original_size = image.size
                image.thumbnail((MAX_IMAGE_SIZE, MAX_IMAGE_SIZE), Image.Resampling.LANCZOS)
                st.info(
                    f"이미지 최적화: {original_size[0]}×{original_size[1]} → "
                    f"{image.size[0]}×{image.size[1]} pixels"
                )
                
            return image
            
        except Exception as e:
            st.error(f"이미지 처리 오류: {e}")
            return None
        
    @staticmethod
    def get_image_info(uploaded_file, image: Image.Image) -> str:
        """이미지 정보를 문자열로 반환"""
        file_size = len(uploaded_file.getvalue()) / 1024
        return (
            f"크기: {image.size[0]}×{image.size[1]} | "
            f"용량: {file_size:.1f}KB | "
            f"형식: {image.format or 'Unknown'}"
        )

class IngredientsDisplayer:
    """성분 표시 통합 클래스"""
    
    @staticmethod
    def display_complete_analysis(ingredients_list: List[str], 
                                analysis_time: Optional[float] = None,
                                prefix_key: str = "") -> None:
        """성분 분석 결과를 완전히 표시 (통합 함수)"""
        if not ingredients_list:
            st.warning("추출된 성분이 없습니다.")
            return
        
        # 성분 목록 표시
        st.markdown("### 📋 추출된 성분 목록")
        IngredientsDisplayer._display_ingredients_grid(ingredients_list)
        
        # 통계 정보
        IngredientsDisplayer._display_statistics(ingredients_list, analysis_time)
        
        # 편집 섹션
        IngredientsDisplayer._display_edit_section(ingredients_list, prefix_key)
        
        # 다운로드 섹션  
        IngredientsDisplayer._display_download_section(ingredients_list, analysis_time, prefix_key)
    
    @staticmethod
    def _display_ingredients_grid(ingredients_list: List[str]) -> None:
        """성분을 그리드 형태로 표시"""
        if len(ingredients_list) <= 10:
            # 단일 열
            for i, ingredient in enumerate(ingredients_list, 1):
                st.markdown(f"**{i}.** {ingredient}")
        else:
            # 두 열로 분할
            col1, col2 = st.columns(2)
            half = (len(ingredients_list) + 1) // 2
            
            with col1:
                for i in range(half):
                    st.markdown(f"**{i+1}.** {ingredients_list[i]}")
            
            with col2:
                for i in range(half, len(ingredients_list)):
                    st.markdown(f"**{i+1}.** {ingredients_list[i]}")
    
    @staticmethod
    def _display_statistics(ingredients_list: List[str], analysis_time: Optional[float] = None) -> None:
        """통계 정보 표시"""
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("총 성분 수", len(ingredients_list))
            
        with col2:
            avg_length = sum(len(ingredient) for ingredient in ingredients_list) / len(ingredients_list)
            st.metric("평균 글자 수", f"{avg_length:.1f}")
                
        with col3:
            longest = max(ingredients_list, key=len)
            st.metric("가장 긴 성분", f"{len(longest)}자")
    
    @staticmethod
    def _display_edit_section(ingredients_list: List[str], prefix_key: str = "") -> None:
        """성분 편집 섹션"""
        with st.expander("✏️ 성분 목록 수정"):
            edited_ingredients = st.text_area(
                "성분 목록 (한 줄에 하나씩):",
                key=f"{prefix_key}edit_area",
                value="\n".join(ingredients_list),
                height=200,
                help="성분을 수정, 추가, 삭제할 수 있습니다."
            )
            
            if st.button("📝 수정 적용", key=f"{prefix_key}apply_edit"):
                logger.info(f"[Streamlit] '수정 적용' 버튼 클릭 - 원본 성분 수: {len(ingredients_list)}")
                modified_list = [line.strip() for line in edited_ingredients.split('\n') if line.strip()]
                st.session_state.current_ingredients = modified_list
                SessionStateManager.reset_chatbot()
                logger.info(f"[Streamlit] 성분 목록 수정 완료 - 수정된 성분 수: {len(modified_list)}")
                st.success(f"성분 목록 수정 완료 ({len(modified_list)}개)")
                st.rerun()
                
    @staticmethod
    def _display_download_section(ingredients_list: List[str], 
                                analysis_time: Optional[float] = None,
                                prefix_key: str = "") -> None:
        """다운로드 섹션"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 다운로드 데이터 준비
        downloads = {
            "numbered": "\n".join(f"{i+1}. {ingredient}" for i, ingredient in enumerate(ingredients_list)),
            "simple": "\n".join(ingredients_list),
            "json": json.dumps({
                "analysis_date": datetime.now().isoformat(),
                "total_count": len(ingredients_list),
                "ingredients": ingredients_list,
                "analysis_time_seconds": analysis_time
            }, ensure_ascii=False, indent=2)
        }
        
        # 다운로드 버튼
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.download_button(
                "📥 번호 포함",
                downloads["numbered"],
                f"ingredients_numbered_{timestamp}.txt",
                key=f"{prefix_key}download_numbered"
            ):
                logger.info(f"[Streamlit] '번호 포함' 다운로드 버튼 클릭 - 성분 수: {len(ingredients_list)}")
        
        with col2:
            if st.download_button(
                "📝 간단 목록",
                downloads["simple"], 
                f"ingredients_simple_{timestamp}.txt",
                key=f"{prefix_key}download_simple"
            ):
                logger.info(f"[Streamlit] '간단 목록' 다운로드 버튼 클릭 - 성분 수: {len(ingredients_list)}")
            
        with col3:
            if st.download_button(
                "📊 JSON 데이터",
                downloads["json"],
                f"ingredients_{timestamp}.json",
                "application/json",
                key=f"{prefix_key}download_json"
            ):
                logger.info(f"[Streamlit] 'JSON 데이터' 다운로드 버튼 클릭 - 성분 수: {len(ingredients_list)}")
        
        # 복사용 텍스트
        with st.expander("📋 복사용 텍스트"):
            st.text_area(
                "복사하세요:",
                downloads["simple"],
                height=150,
                disabled=True,
                key=f"{prefix_key}copy_area"
            )

class ChatbotAnalyzer:
    """챗봇 분석 통합 클래스"""
    
    @staticmethod
    def display_analysis_section(ingredients_list: List[str]) -> None:
        """챗봇 분석 섹션 표시"""
        if not ingredients_list:
            st.warning("분석할 성분이 없습니다.")
            return
        
        # 현재 성분 목록이 변경되었는지 확인
        current_ingredients_key = "_".join(ingredients_list)
        last_analyzed_key = st.session_state.get('last_analyzed_ingredients_key', '')
        
        # 성분이 변경되었다면 챗봇 상태 초기화
        if current_ingredients_key != last_analyzed_key:
            st.session_state.chatbot_analyzed = False
            st.session_state.chatbot_result = None
            st.session_state.last_analyzed_ingredients_key = current_ingredients_key
        
        # 분석 버튼 또는 결과 표시
        if not st.session_state.get('chatbot_analyzed', False):
            if st.button("💬 섭취 가능 여부 확인", use_container_width=True):
                telemetry_info = {
                    "ingredients_count": len(ingredients_list),
                    "user_id": st.session_state.get("user_id"),
                    "username": st.session_state.get("username"),
                    "has_jwt": bool(st.session_state.get("jwt_token")),
                    "use_rag": st.session_state.get("use_rag", True),
                    "auto_clean": st.session_state.get("auto_clean", True)
                }
                logger.info(f"[Streamlit] '섭취 가능 여부 확인' 버튼 클릭 - {telemetry_info}")
                ChatbotAnalyzer._perform_analysis(ingredients_list)
        else:
            # 분석 결과 표시
            if st.session_state.get('chatbot_result'):
                st.success("AI 분석 완료")
                st.info(st.session_state.chatbot_result)
                
                # 재분석 버튼
                if st.button("🔄 다시 분석", key="re_analyze"):
                    logger.info("[Streamlit] '다시 분석' 버튼 클릭 - 챗봇 상태 초기화")
                    st.session_state.chatbot_analyzed = False
                    st.session_state.chatbot_result = None
                    st.rerun()
    
    @staticmethod
    def _perform_analysis(ingredients_list: List[str]) -> None:
        """챗봇 분석 실행"""
        with st.spinner("AI가 성분을 분석하고 있습니다..."):
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    api_url = os.getenv("API_URL")
                    if not api_url:
                        raise RuntimeError("API_URL 환경 변수가 설정되지 않았습니다")

                    user_id = st.session_state.get("user_id")
                    if not user_id:
                        raise RuntimeError("사용자 ID가 없습니다. 로그인 후 이용해주세요.")

                    # UUID 검증 및 변환
                    try:
                        from uuid import UUID
                        # 먼저 UUID 형식인지 확인
                        user_uuid = UUID(str(user_id))
                    except ValueError:
                        # UUID가 아닌 경우 (소셜 로그인 ID 등), 문자열 그대로 사용
                        logger.info(f"[Streamlit] UUID가 아닌 사용자 ID 형식 감지: {user_id}")
                        user_uuid = str(user_id)

                    payload = {
                        "ingredients": ingredients_list,
                        "user_id": str(user_uuid),  # UUID를 문자열로 변환
                        "image_url": st.session_state.get("current_image_path"),  # 저장된 이미지 경로
                        "ocr_result": st.session_state.get("current_ocr_result")
                    }
                    
                    # 디버그 로그 추가
                    logger.info(f"[Streamlit] 챗봇 분석 요청 - image_url: {st.session_state.get('current_image_path')}")
                    logger.info(f"[Streamlit] 챗봇 분석 요청 - current_image_path 존재: {bool(st.session_state.get('current_image_path'))}")
                    
                    headers = {
                        "Content-Type": "application/json",
                        "X-User-Id": str(user_uuid)
                    }
                    # 선택적으로 JWT 포함
                    if st.session_state.get("jwt_token"):
                        headers["Authorization"] = f"Bearer {st.session_state['jwt_token']}"

                    logger.info(f"[Streamlit] /analyze/chatbot/ 호출 시작 (시도 {retry_count + 1}/{max_retries}) - user_id={user_uuid}, ingredients_count={len(ingredients_list)}")
                    resp = requests.post(
                        f"{api_url.rstrip('/')}/analyze/chatbot/",
                        json=payload,
                        headers=headers,
                        timeout=60
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    st.session_state.chatbot_result = data.get("chatbot_result") or data.get("message")
                    st.session_state.chatbot_analyzed = True
                    st.session_state.last_saved_log_id = data.get("user_food_log_id")
                    logger.info(f"[Streamlit] 분석 완료 및 저장됨: log_id={st.session_state.get('last_saved_log_id')}")
                    break  # 성공하면 루프 종료

                except requests.exceptions.RequestException as e:
                    retry_count += 1
                    logger.error(f"백엔드 호출 실패 (시도 {retry_count}/{max_retries}): {e}")
                    
                    if retry_count >= max_retries:
                        if hasattr(e, 'response') and e.response is not None:
                            try:
                                error_detail = e.response.json()
                                st.error(f"서버 오류 (최종): {error_detail.get('detail', str(e))}")
                                logger.error(f"서버 응답 상세: {error_detail}")
                            except:
                                st.error(f"서버 통신 오류 (최종): {e}")
                        else:
                            st.error(f"서버 통신 오류 (최종): {e}")
                    else:
                        st.warning(f"서버 통신 실패, 재시도 중... ({retry_count}/{max_retries})")
                        import time
                        time.sleep(2)  # 2초 대기 후 재시도
                        
                except Exception as e:
                    st.error(f"분석 중 오류 발생: {e}")
                    logger.error(f"챗봇 분석 오류: {e}")
                    break  # 예상치 못한 오류는 재시도하지 않음

class AnalysisHistoryManager:
    """분석 기록 관리 클래스"""
    
    @staticmethod
    def save_to_history(image_name: str, ingredients_count: int, analysis_time: float) -> None:
        """분석 결과를 기록에 저장"""
        history_item = {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'image_name': image_name,
            'ingredients_count': ingredients_count,
            'analysis_time': analysis_time
        }
        
        st.session_state.analysis_history.append(history_item)
        
        # 최대 크기 제한
        if len(st.session_state.analysis_history) > MAX_HISTORY_SIZE:
            st.session_state.analysis_history.pop(0)
    
    @staticmethod
    def display_sidebar_history() -> None:
        """사이드바에 기록 표시"""
        if not st.session_state.analysis_history:
            return
        
        st.markdown("### 📈 분석 기록")
        recent_records = list(reversed(st.session_state.analysis_history[-5:]))
        
        for record in recent_records:
            with st.expander(f"{record['image_name'][:20]}...", expanded=False):
                st.text(f"시간: {record['timestamp']}")
                st.text(f"성분 수: {record['ingredients_count']}개")
                st.text(f"분석 시간: {record['analysis_time']:.1f}초")
    
        if st.button("🗑️ 기록 초기화"):
            logger.info("[Streamlit] '기록 초기화' 버튼 클릭")
            AnalysisHistoryManager.clear_history()
            
    @staticmethod
    def clear_history() -> None:
        """기록 초기화"""
        st.session_state.analysis_history = []
        st.session_state.current_ingredients = []
        SessionStateManager.reset_chatbot()
        st.success("기록이 초기화되었습니다.")
        st.rerun()