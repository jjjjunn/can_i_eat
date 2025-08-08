import streamlit as st
from PIL import Image
import numpy as np
import time
import os
import tempfile # 임시 파일 생성 위함
import json
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import sys

# .env 로드
load_dotenv()

# .env의 PYTHONPATH를 sys.path에 반영
python_path = os.getenv("PYTHONPATH")
if python_path and python_path not in sys.path:
    sys.path.append(os.path.abspath(python_path))

# services 모듈 가져오기
from services.ocr_service import VisionTextExtractor
from services.chatbot import IngredientsAnalyzer
from services.rag import OptimizedRAGSystem, RAGSystem


# 앱 실행 시 프로젝트 루트에서 실행할 것
# streamlit run streamlit_app/v1.2/app.py

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 페이지 설정
st.set_page_config(
    page_title="성분분석기",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 상수 정의
MAX_IMAGE_SIZE = 2048
MAX_HISTORY_SIZE = 10
SUPPORTED_TYPES = ["jpg", "jpeg", "png", "jfif", "webp"]


# RAG 및 챗봇 시스템 초기화: 객체를 세션 상태에 저장하고 재사용하는 방식
# 이벤트 루프 오류를 방지하고 앱의 성능을 최적화 하기 위함
class SessionStateManager:
    """세션 상태 관리 클래스"""
    
    @staticmethod
    def initialize_session_state():
        """세션 상태 초기화"""
        defaults={
            'analysis_history': [],
            'current_ingredients': [],
            'chatbot_analyzed': False,
            'chatbot_result': None,
            'rag_system': None,
            'analyzer': None,
            'initialization_complete': False
        }
        
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
                
    @staticmethod
    def reset_chatbot_state():
        """챗봇 관련 상태 초기화"""
        st.session_state.chatbot_analyzed = False
        st.session_state.chatbot_result = None

class RAGInitializer:
    """RAG 시스템 초기화 클래스"""
    
    @staticmethod
    def initialize_rag_system() -> bool:
        """RAG 시스템 초기화"""
        if st.session_state.get('rag_system') is not None:
            return True
        
        try:
            with st.spinner("RAG 시스템 초기화 중..."):
                # OptimizedRAGSystem을 사용하거나, 필요한 RAG 시스템을 선택하여 초기화
                rag_instance = OptimizedRAGSystem()
                
                # 새로운 동기 함수를 호출하여 초기화 진행
                rag_instance.initialize() # public 메서드 호출
                
                st.session_state.rag_system = rag_instance
                st.info("RAG 시스템 초기화 완료")
                return True
            
        except Exception as e:
            st.error(f"RAG 시스템 초기화 실패: {e}")
            logger.error(f"RAG 시스템 초기화 오류: {e}")
            return False
        
    @staticmethod
    def initialize_analyzer() -> bool:
        """분석기 초기화"""
        if st.session_state.get('analyzer') is not None:
            return True
        try:
            with st.spinner("성분 분석기 초기화 중..."):
                # RAG 시스템 객체를 IngredientsAnalyzer에 전달하여 초기화
                st.session_state.analyzer = IngredientsAnalyzer()
                st.info("성분 분석기 챗봇 초기화 완료")
                logger.info("성분 분석기 챗봇 초기화 완료")
                return True
            
        except Exception as e:
            st.error(f"성분 분석기 챗봇 초기화 실패: {e}")
            logger.error(f"성분 분석기 챗봇 초기화 실패: {e}")
            return False

class ImageProcessor:
    """이미지 처리 클래스"""
    
    @staticmethod
    def process_uploaded_image(uploaded_file) -> Optional[Image.Image]:
        """업로드된 이미지 처리"""
        try:
            image = Image.open(uploaded_file)
            
            # 이미지 리사이즈
            if max(image.size) > MAX_IMAGE_SIZE:
                original_size = image.size
                image.thumbnail((MAX_IMAGE_SIZE, MAX_IMAGE_SIZE), Image.Resampling.LANCZOS)
                st.info(
                    f"이미지 사이즈 최적화: {original_size[0]}x{original_size[1]} -> "
                    f"{image.size[0]} * {image.size[1]} pixels"
                )
                
            return image
            
        except Exception as e:
            st.error(f"이미지 처리 중 오류 발생: {e}")
            return None    
        
    @staticmethod
    def get_image_info(uploaded_file, image: Image.Image) -> Dict[str, Any]:
        """이미지 정보 반환"""
        file_size = len(uploaded_file.getvalue()) / 1024
        return {
            'width': image.size[0],
            'height': image.size[1],
            'file_size_kb': file_size,
            'format': image.format or 'Unknown'
        }

class IngredientsDisplayer:
    """성분 표시 클래스"""
    
    @staticmethod
    def display_ingerdients_list(ingredients_list: List[str]) -> None:
        """성분 목록 표시"""
        if not ingredients_list:
            st.warning("추출된 성분이 없습니다.")
            return
    
        st.markdown("### 📋 추출된 성분 목록")
        
        # 레이아웃 설정
        if len(ingredients_list) <= 10:
            IngredientsDisplayer._display_single_column(ingredients_list)
        else:
            IngredientsDisplayer._display_two_columns(ingredients_list)
    
    @staticmethod
    def _display_single_column(ingredients_list: List[str]) -> None:
        """단일 열로 성분 표시"""
        for i, ingredient in enumerate(ingredients_list, 1):
            st.markdown(f"**{i}.** {ingredient}")

    @staticmethod
    def _display_two_columns(ingredients_list: List[str]) -> None:
        """두 열로 표시"""
        col1, col2 = st.columns(2)
        half = (len(ingredients_list) + 1) // 2 # 홀수 개수일 때 한쪽이 더 많도록
        
        with col1:
            for i in range(half):
                st.markdown(f"**{i+1}.** {ingredients_list[i]}")
        
        with col2:
            for i in range(half, len(ingredients_list)):
                st.markdown(f"**{i+1}.** {ingredients_list[i]}")
    
    @staticmethod
    def display_statistics(ingredients_list: List[str], analysis_time: Optional[float] = None) -> None:
        """통계 정보 표시"""
        if not ingredients_list:
            return
        
        st.markdown("---")
    
        col_1, col_2, col_3 = st.columns(3) # col_stat4 
        with col_1:
            st.metric("총 성분 수", len(ingredients_list))
            
        with col_2:
            if ingredients_list:
                avg_length = sum(len(ingredient) for ingredient in ingredients_list) / len(ingredients_list)
                st.metric("평균 글자 수", f"{avg_length:.1f}")
                
        with col_3:
            longest = max(ingredients_list, key=len) if ingredients_list else ""
            st.metric("가장 긴 성분", f"{len(longest)}자")
        # with col_stat4:
        #     if analysis_time:
        #         st.metric("분석 시간", f"{analysis_time:.1f}초")
            
    
    @staticmethod
    def display_edit_section(ingredients_list: List[str], prefix_key: str = "") -> List[str]:
        """편집 섹션 표시"""
        with st.expander("✏️ 성분 목록 수정"):
            st.markdown("**추출된 성분을 직접 편집할 수 있습니다.:**")
            
            edited_ingredients = st.text_area(
                "성분 목록 (한 줄에 하나씩):",
                key=f"{prefix_key}ingredients_text_area_edit",
                value="\n".join(ingredients_list),
                height=200,
                help="불필요한 성분을 삭제하거나 누락된 성분을 추가할 수 있습니다."
            )
            
            if st.button("📝 수정 적용", key=f"{prefix_key}apply_edit_button"):
                modified_list = [
                    line.strip() for line in edited_ingredients.split('\n')
                    if line.strip()
                ]
                
                st.session_state.current_ingredients = modified_list
                SessionStateManager.reset_chatbot_state()
                st.success(f"성분 목록이 수정되었습니다. ({len(modified_list)}개 성분")
                st.rerun()
                
        return ingredients_list
             
    @staticmethod
    def display_download_section(ingredients_list: List[str],
                                 analysis_time: Optional[float] = None,
                                 prefix_key: str ="") -> None:
        
        """다운로드 섹션 표시"""
        if not ingredients_list:
            return
        
        # 결과 다운로드 옵션
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 다양한 형태의 데이터 준비
        ingredients_numbered = "\n".join([
            f"{i+1}, {ingredient}" for i, ingredient in enumerate(ingredients_list)
        ])
        ingredients_simple = "\n".join(ingredients_list)
        
        # JSON 형태로도 다운로드 가능
        ingredients_json = {
            "analysis_date": datetime.now().isoformat(),
            "total_count": len(ingredients_list),
            "ingredients": ingredients_list,
            "analysis_time_seconds": analysis_time
        }
        
        # 다운로드 버튼
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.download_button(
                label="📥 번호 포함 다운로드",
                data=ingredients_numbered,
                file_name=f"ingredients_numbered_{current_time}.txt",
                mime="text/plain",
                use_container_width=True,
                key=f"{prefix_key}download_numbered"
            )
        
        with col2:
            st.download_button(
                label="📝 간단 목록 다운로드", 
                data=ingredients_simple,
                file_name=f"ingredients_simple_{current_time}.txt",
                mime="text/plain",
                use_container_width=True,
                key=f"{prefix_key}download_simple"
            )
            
        with col3:
            st.download_button(
                label="📊 JSON 다운로드",
                data=json.dumps(ingredients_json, ensure_ascii=False, indent=2),
                file_name=f"ingredients_data_{current_time}.json",
                mime="application/json",
                use_container_width=True,
                key=f"{prefix_key}download_json"
            )
        
        # 복사용 텍스트 박스
        with st.expander("📋 복사용 텍스트"):
            st.text_area(
                "아래 텍스트를 복사하세요:",
                value=ingredients_simple,
                height=150,
                disabled=True, # 사용자 직접 수정 불가
                key=f"{prefix_key}ingredients_text_area_copy"
            )
        
class ChatbotIntegration:
    """챗봇 연동 클래스"""
    
    @staticmethod
    def display_chatbot_analysis(ingredients_list: List[str]) -> None:
        """챗봇 분석 표시"""
        if not ingredients_list:
            st.warning("추출된 성분이 없어 분석을 할 수 없습니다.")
            return
        
        if not st.session_state.get('chatbot_analyzed', False):   
            # 챗봇 분석이 완료되지 않았거나, 다시 분석 버튼이 눌렸을 때만 분석 시도
            # 수정 적용 버튼 클릭 시에도 'chatbot_analyzed'가 False로 리셋되도록 display_ingredients 함수에서 처리
            if st.button("💬 섭취 가능 여부 확인",
                         key="chatbot_analysis_button",
                         use_container_width=True
                         ):
                ChatbotIntegration._perform_analysis(ingredients_list)
                
        # 분석 결과 표시
        if (st.session_state.get('chatbot_analyzed', False) and
            st.session_state.get('chatbot_result')):
            st.success("AI 분석 완료")
            st.info(st.session_state.chatbot_result)
            
    @staticmethod
    def _perform_analysis(ingredients_list: List[str]) -> None:
        """실제 분석 시행"""      
        with st.spinner("AI 챗봇이 성분표를 분석 중입니다... 잠시만 기다려 주세요."):
            try:
                # IngredientAnalyzer 객체 생성
                analyzer = st.session_state.analyzer
                rag_system = st.session_state.rag_system
                # RAG 사용 여부 선택
                use_rag = st.session_state.get('use_rag', True) # 사이드바에 체크 박스
                
                # 객체를 통해 analyze_ingredients 메서드 호출
                chatbot_result = analyzer.analyze_ingredients(
                    ingredients_list=ingredients_list,
                    use_rag=use_rag,
                    rag_system=rag_system
                )
                
                st.session_state.chatbot_result = chatbot_result
                st.session_state.chatbot_analyzed = True # 분석 완료 플래스 설정
                st.rerun()
                
            except Exception as e:
                st.error(f"챗봇 분석 중 오류 발생: {e}")
                logger.error(f"챗봇 분석 오류: {e}")
                st.session_state.chatbot_analyzed = False # 오류 발생 시 플래그 리셋
                    

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
    def display_history_sidebar() -> None:
        """사이드바에 기록 표시"""
        if not st.session_state.analysis_history:
            return
        
        st.markdown("### 📈 분석 기록")
        recent_records = list(reversed(st.session_state.analysis_history[-5:])) # 최근 5개만 표시
        
        for record in recent_records: 
            with st.expander(f"{record['image_name'][:20]}...", expanded=False):
                st.text(f"시간: {record['timestamp']}")
                st.text(f"성분 수: {record['ingredients_count']}개")
                st.text(f"분석 시간: {record['analysis_time']:.1f}초")
    
        if st.button("🗑️ 기록 초기화", key="clear_history_button"):
            AnalysisHistoryManager.clear_history()
            st.success("분석 기록이 초기화되었습니다.")
            
    @staticmethod
    def clear_history() -> None:
        """기록 초기화"""
        st.session_state.analysis_history = []
        st.session_state.current_ingredients = []
        SessionStateManager.reset_chabot_state()
        st.success("분석 기록이 초기화되었습니다.")
        st.rerun()

def display_ingredients(ingredients_list: List[str],
                        analysis_time: Optional[float] = None,
                        prefix_key: str = "") -> None:
    """통합 성분 표시 함수"""
    displayer = IngredientsDisplayer()
    
    displayer.display_ingerdients_list(ingredients_list)
    displayer.display_statistics(ingredients_list, analysis_time)
    displayer.display_edit_section(ingredients_list, prefix_key)
    displayer.display_download_section(ingredients_list, analysis_time, prefix_key)

def create_sidebar() -> Dict[str, Any]:
    """사이드바 생성"""
    with st.sidebar:
        
        st.markdown("### ⚙️ 설정")
        
        # 옵션 설정
        settings = {
            'show_progress': st.checkbox("진행률 표시", value=True),
            'auto_clean': st.checkbox("자동 성분 정리", value=True,
                                      help="의미없는 텍스트를 자동으로 제거"),
            'use_rag': st.checkbox("RAG 기능 사용하기", value=True,
                                   help="논문에서 정보 가져오기")
        }
        # show_detailed_results = st.checkbox("상세 결과 표시", value=True)
        st.session_state.update(settings)
        st.markdown("---")
        
        # 분석 기록
        AnalysisHistoryManager.display_history_sidebar()
        st.markdown("---")
        
        # 사용 팁
        st.markdown("### 💡 사용 팁")
        st.markdown("""
        - **고해상도 이미지** 사용 권장
        - **글자가 선명한** 이미지가 좋음  
        - **배경과 대비**가 뚜렷한 이미지
        - **기울어지지 않은** 정면 촬영
        - **조명이 충분한** 환경에서 촬영
        """)
        
        return settings

def analyze_image(image:Image.Image, uploaded_file, settings: Dict[str, Any]) -> None:
    """이미지 분석 수행"""
    SessionStateManager.reset_chatbot_state()
    # 진행률 표시 설정
    # Streamlit 의 progress bar와 status text를 위한 변수 초기화
    progress_bar = None
    status_text = None
    
    if settings['show_progress']:
        rogress_bar = st.progress(0, "분석 준비 중...") # 초기 0%
        status_text = st.empty()

    # progress_callback 함수 정의
    def progress_updater(value: int, message: str) -> None:
        """진행률 업데이트"""
        if progress_bar:
            progress_bar.progress(value / 100, text = message)
        if status_text:
            status_text.text(f"상태: {message}")
    
    start_time = time.time()
    
    tmp_file_path = "" # finally 블록에서 사용하기 위해 초기화

    # 이미지 파일을 임시로 저장하여 경로를 넘겨주는 로직
    # Google Vision API는 파일 경로를 받거나 바이트 데이터를 받음
    # UploadedFile 객체는 직접 경로 없음
    
    try:
        # 임시파일 생성
        with tempfile.NamedTemporaryFile(
            delete=False, 
            suffix=Path(uploaded_file.name).suffix
            ) as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_file_path = tmp_file.name # 임시 파일 경로

        # OCR 처리: extract_ingredients_with_progress 함수 호출
        extractor = VisionTextExtractor(api_endpoint='eu-vision.googleapis.com')
        extracted_list = extractor.extract_ingredients_with_progress(
            tmp_file_path, progress_updater # 콜백 함수
        )
        
        # 자동 정리 옵션이 켜져 있으면 성분 목록 정리
        if settings['auto_clean']:
            progress_updater(95, "성분 목록 정리 중...")
            extracted_list = extractor.clean_and_filter_ingredients(extracted_list)
        
        # 진행률 표시 정리
        if progress_bar:
            progress_bar.empty()
        if status_text:
            status_text.empty()
            
        end_time = time.time()
        processing_time = end_time - start_time
        
        # 결과 처리
        if extracted_list:
            st.success(
                f"✅ {len(extracted_list)}개 성분 추출 완료!"
                f"{processing_time:.1f}초 소요)"
            )
            
            # 세션 상태 업데이트
            st.session_state.current_ingredients = extracted_list
            
            # 기록 저장
            AnalysisHistoryManager.save_to_history(
                uploaded_file.name,
                len(extracted_list),
                processing_time
            )
            
            # 결과 표시
            display_ingredients(extracted_list, processing_time)
            
            # 챗봇 연동 함수 호출
            st.markdown("---")
            st.subheader("🤖 AI 챗봇 분석")
            ChatbotIntegration.display_chatbot_analysis(extracted_list)
            
        else:
            st.warning("성분을 추출하지 못했습니다.")
            
    except Exception as e:
                # 오류 발생 시 진행 바와 상태 텍스트 비움
                if progress_bar:
                    progress_bar.empty()
                if status_text:
                    status_text.empty()
                    
                st.error(f"분석 중 오류가 발생했습니다: {e}")
                st.info(
                    "💡 문제 해결 방법:\n"
                    "- 이미지 품질을 확인해주세요\n"
                    "- 다른 이미지로 시도해보세요\n"
                    "- API 키 설정을 확인해주세요"
                )
                logger.info(f"이미지 분석 오류: {e}")
                
    finally:
        # 임시 파일 삭제
        if tmp_file_path and os.path.exists(tmp_file_path):
            try: 
                os.remove(tmp_file_path)
            except Exception as e:
                logger.waring(f"임시 파일 삭제 실패: {e}")
                
def display_usage_guide() -> None:
    # 사용법 가이드
    with st.expander("📖 사용법 가이드"):
        st.markdown("""
        ### 🎯 최적의 결과를 위한 팁
        
        1. **이미지 품질**
           - 300 DPI 이상의 고해상도 이미지 사용
           - 흐릿하지 않은 선명한 이미지
           - 파일 크기: 1MB 이하 권장
           
        2. **촬영 조건**  
           - 충분한 조명 확보
           - 그림자나 반사 최소화
           - 정면에서 수직으로 촬영
           - 손떨림 방지
           
        3. **성분표 포맷**
           - "성분:", "Ingredients:", "원재료명:" 등 명확한 시작 키워드
           - 글자 크기가 너무 작지 않은 이미지
           
        4. **결과 확인 및 편집**
           - 추출된 성분 목록을 검토하여 오인식 수정
           - 수동 편집 기능으로 불필요한 내용 제거
           - 다양한 형태로 다운로드 가능
           
        ### 🔧 문제 해결
        - **성분이 추출되지 않을 때**: 이미지 품질 확인, 다른 각도로 재촬영
        - **오인식이 많을 때**: 자동 정리 기능 활용, 수동 편집으로 수정
        - **처리 속도가 느릴 때**: 이미지 크기를 줄여서 재시도
        """)

def display_system_status() -> None:
    """시스템 상태 표시"""
    with st.expander("🔧 시스템 상태"):
        if os.environ.get('GOOGLE_API_KEY'):
            st.success("✅ Google API 키가 설정되어 있습니다.")
        else:
            st.error("❌ Google API 키가 설정되지 않았습니다.")
            st.code("GOOGLE_API_KEY 환경변수를 설정해주세요.")
            
        # RAG 시스템 상태
        if st.session_state.get('rag_system'):
            if st.session_state.rag_system.is_initialized():
                st.success("RAG 시스템이 정상 작동 중입니다.")
            else:
                st.warning("RAG 시스템이 초기화되지 않았습니다.")
                
        else:
            st.error("RAG 시스템을 이용할 수 없습니다.")
            
        # 분석기 상태
        if st.session_state.get('analyzer'):
            st.success("성분 분석기가 준비되었습니다.")
        else:
            st.error("성분 분석기를 사용할 수 없습니다.")

# 세션 상태 초기화
SessionStateManager.initialize_session_state()
# Streamlit은 스크립트의 main 함수가 호출되는 방식이 아니라,
# 스크립트 파일 자체를 위에서 아래로 실행
# main() 함수 안에 초기화 코드가 있더라도,
# main() 함수가 호출되기 전에 다른 전역 코드에서 st.session_state에 접근한다면
# 초기화가 되지 않은 상태로 실행될 수 있음

def main():
    """메인 어플리케이션"""
    
    # 시스템 초기화 (한 번만 실행)
    if not st.session_state.get('initialization_complete', False):
        st.info("시스템을 초기화하고 있습니다.")
        
        # RAG 시스템 초기화
        if not RAGInitializer.initialize_rag_system():
            st.stop()
            
        # 분석기 초기화
        if not RAGInitializer.initialize_analyzer():
            st.stop()
            
        st.session_state.initialization_complete = True
        st.success("시스템 초기화 완료")
        st.rerun()

# UI 구성            
st.title("🔍 이미지 성분 분석기 (Google Vision API)")
st.markdown("AI 기반 고성능 OCR로 성분표를 정확하게 분석합니다.")

# 사이드바 구성
settings = create_sidebar()

st.subheader("📷 이미지 업로드")
uploaded_file = st.file_uploader(
    "성분표 이미지를 선택하세요", 
    type=SUPPORTED_TYPES,
    help=f"지원 형식: {', '.join(f.upper() for f in SUPPORTED_TYPES)}"
)

# 파일 업로드 후 로직
if uploaded_file is not None:
    # 이미지 처리
    image = ImageProcessor.process_uploaded_image(uploaded_file)
    
    if image:
        st.image(image, caption="업로드된 이미지", use_container_width=True)
        
        # 이미지 정보 표시
        info = ImageProcessor.get_image_info(uploaded_file, image)
        st.info(
            f"이미지 크기: {info['width']} x {info['height']} pixels | "
            f"파일 크기: {info['file_size_kb']:.1f}KB | "
            F"형식: {info['format']}"
        )   
        st.markdown("---")

# 분석 시작 버튼 및 결과 표시

# if uploaded_file is not None and image:
#     st.subheader("🔍 분석 결과")
    
# 분석 시작 버튼
if st.button("🚀 분석 시작", type="primary",
                use_container_width=True, key="start_analysis_button"):
    analyze_image(image, uploaded_file, settings)

# 이전 결과가 있으면 다시 표시
elif st.session_state.get('current_ingredients'):
    st.markdown("---")
    st.markdown("### 📋 현재 분석 결과")
    display_ingredients(
        st.session_state.current_ingredients,
        prefix_key="previous_"
    )
            
    # 챗봇 분석
    st.markdown("---")
    st.subheader("🤖 AI 챗봇 분석")
    ChatbotIntegration.display_chatbot_analysis(
        st.session_state.current_ingredients
    )

#uploaded_file이 None 일 때만 표시
else: 
    st.info("☝🏻 성분표 이미지를 업로드해주세요")
    display_usage_guide()
    display_system_status()

# footer
st.markdown("---")
st.caption("🚀 Powered by Streamlit, Google Gemini & Google Cloud Vision")
    
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"애플리케이션 실행 중 오류가 발생했습니다.: {e}")

        logger.error(f"앱 실행 오류: {e}", exc_info=True)
