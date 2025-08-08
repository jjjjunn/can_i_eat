import streamlit as st
from PIL import Image
import numpy as np
import easyocr
import time
from services.ocr_service import (
    extract_ingredients_easyocr, 
    extract_ingredients_tesseract,
    extract_ingredients_advanced,
    extract_ingredients_with_confidence,
    extract_ingredients_easyocr_with_progress,
    extract_ingredients_tesseract_with_progress,
    extract_ingredients_combined_with_progress,
    set_processor_reader
)

# Reader를 캐싱하여 매번 다시 로드하지 않도록 함
@st.cache_resource
def get_easyocr_reader():
    """EasyOCR Reader를 로드하고 캐싱"""
    reader = easyocr.Reader(['ko', 'en'], gpu=False)
    # OCR 서비스에 캐싱된 reader 설정
    set_processor_reader(reader)
    return reader

# 페이지 설정
st.set_page_config(
    page_title="향상된 성분분석기",
    page_icon="🔍",
    layout="wide"
)

# EasyOCR Reader 초기화 (캐싱됨)
reader = get_easyocr_reader()

st.title("🔍 향상된 이미지 성분 분석기")
st.markdown("AI 기반 고성능 OCR로 성분표를 정확하게 분석합니다.")

def display_ingredients(ingredients_list):
    """성분 목록을 보기 좋게 표시하는 함수"""
    if not ingredients_list:
        st.warning("추출된 성분이 없습니다.")
        return
    
    st.markdown("### 📋 추출된 성분 목록")
    
    # 성분 개수에 따라 다른 레이아웃 적용
    if len(ingredients_list) <= 10:
        # 적은 수의 성분은 세로로 나열
        for i, ingredient in enumerate(ingredients_list, 1):
            st.markdown(f"**{i}.** {ingredient}")
    else:
        # 많은 성분은 2열로 표시
        col1, col2 = st.columns(2)
        half = len(ingredients_list) // 2
        
        with col1:
            for i in range(half):
                st.markdown(f"**{i+1}.** {ingredients_list[i]}")
        
        with col2:
            for i in range(half, len(ingredients_list)):
                st.markdown(f"**{i+1}.** {ingredients_list[i]}")
    
    st.markdown("---")
    
    # 통계 정보
    col_stat1, col_stat2, col_stat3 = st.columns(3)
    with col_stat1:
        st.metric("총 성분 수", len(ingredients_list))
    with col_stat2:
        avg_length = sum(len(ingredient) for ingredient in ingredients_list) / len(ingredients_list)
        st.metric("평균 글자 수", f"{avg_length:.1f}")
    with col_stat3:
        longest = max(ingredients_list, key=len) if ingredients_list else ""
        st.metric("가장 긴 성분", f"{len(longest)}자")
    
    # 결과 다운로드 옵션
    ingredients_text = "\n".join([f"{i+1}. {ingredient}" for i, ingredient in enumerate(ingredients_list)])
    
    col_download1, col_download2 = st.columns(2)
    with col_download1:
        st.download_button(
            label="📥 번호 포함 다운로드",
            data=ingredients_text,
            file_name="extracted_ingredients_numbered.txt",
            mime="text/plain",
            use_container_width=True
        )
    
    with col_download2:
        ingredients_simple = "\n".join(ingredients_list)
        st.download_button(
            label="📝 간단 목록 다운로드", 
            data=ingredients_simple,
            file_name="extracted_ingredients_simple.txt",
            mime="text/plain",
            use_container_width=True
        )
    
    # 복사용 텍스트 박스
    with st.expander("📋 복사용 텍스트"):
        st.text_area(
            "아래 텍스트를 복사하세요:",
            value=ingredients_simple,
            height=150,
            disabled=True
        )

# 사이드바 설정
with st.sidebar:
    st.header("⚙️ 설정")
    
    # OCR 엔진 선택
    ocr_engine_choice = st.selectbox(
        "OCR 엔진 선택:",
        (
            "향상된 EasyOCR", 
            "향상된 Tesseract", 
            "결합 모드 (추천)",
            "기본 EasyOCR (이전 버전)",
            "기본 Tesseract (이전 버전)"
        ),
        index=2
    )
    
    # 고급 옵션
    st.markdown("---")
    show_progress = st.checkbox("진행률 표시", value=True)
    show_detailed_results = st.checkbox("상세 결과 표시", value=True)
    
    st.markdown("---")
    st.markdown("### 💡 사용 팁")
    st.markdown("""
    - **고해상도 이미지** 사용 권장
    - **글자가 선명한** 이미지가 좋음  
    - **배경과 대비**가 뚜렷한 이미지
    - **기울어지지 않은** 정면 촬영
    - **결합 모드**가 가장 정확함
    """)
    
    st.markdown("---")
    st.markdown("### 🆕 새로운 기능")
    st.markdown("""
    - ✨ **다중 전처리**: 5가지 전처리 방식 적용
    - 🔄 **결합 모드**: 두 엔진 결과 병합
    - 📊 **진행률 표시**: 실시간 처리 상황
    - 📈 **상세 결과**: 각 엔진별 비교
    """)

# 메인 영역
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📷 이미지 업로드")
    uploaded_file = st.file_uploader(
        "성분표 이미지를 선택하세요", 
        type=["jpg", "jpeg", "png", "jfif"]
    )

    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption='업로드된 이미지', use_container_width=True)
        
        # 이미지 정보 표시
        st.info(f"📏 이미지 크기: {image.size[0]} x {image.size[1]} pixels")

with col2:
    if uploaded_file is not None:
        st.subheader("🔍 분석 결과")
        
        # 분석 시작 버튼
        if st.button("🚀 분석 시작", type="primary", use_container_width=True):
            image_array = np.array(image)
            
            # 진행률 표시 설정
            progress_bar = None
            status_text = None
            if show_progress:
                progress_bar = st.progress(0, "분석 준비 중...")
                status_text = st.empty()
            
            def progress_callback(progress, message):
                if progress_bar:
                    progress_bar.progress(progress, message)
                if status_text:
                    status_text.text(f"상태: {message}")
            
            start_time = time.time()
            
            try:
                if ocr_engine_choice == "향상된 EasyOCR":
                    if show_progress:
                        extracted_list = extract_ingredients_easyocr_with_progress(
                            image_array, progress_callback
                        )
                    else:
                        extracted_list = extract_ingredients_easyocr(image_array)
                    
                    if progress_bar:
                        progress_bar.empty()
                    if status_text:
                        status_text.empty()
                        
                    end_time = time.time()
                    processing_time = end_time - start_time
                    
                    if extracted_list:
                        st.success(f"✅ 향상된 EasyOCR로 {len(extracted_list)}개 성분 추출 완료! ({processing_time:.1f}초)")
                        display_ingredients(extracted_list)
                    else:
                        st.warning("성분을 추출하지 못했습니다.")
                        
                elif ocr_engine_choice == "향상된 Tesseract":
                    if show_progress:
                        extracted_list = extract_ingredients_tesseract_with_progress(
                            image_array, progress_callback
                        )
                    else:
                        extracted_list = extract_ingredients_tesseract(image_array)
                    
                    if progress_bar:
                        progress_bar.empty()
                    if status_text:
                        status_text.empty()
                        
                    end_time = time.time()
                    processing_time = end_time - start_time
                    
                    if extracted_list:
                        st.success(f"✅ 향상된 Tesseract로 {len(extracted_list)}개 성분 추출 완료! ({processing_time:.1f}초)")
                        display_ingredients(extracted_list)
                    else:
                        st.warning("성분을 추출하지 못했습니다.")
                        
                elif ocr_engine_choice == "결합 모드 (추천)":
                    if show_progress:
                        results = extract_ingredients_combined_with_progress(
                            image_array, progress_callback
                        )
                    else:
                        results = extract_ingredients_with_confidence(image_array)
                    
                    if progress_bar:
                        progress_bar.empty()
                    if status_text:
                        status_text.empty()
                        
                    end_time = time.time()
                    processing_time = end_time - start_time
                    
                    if results['combined']:
                        st.success(f"✅ 결합 모드로 {results['combined_count']}개 성분 추출 완료! ({processing_time:.1f}초)")
                        
                        # 상세 결과 표시
                        if show_detailed_results:
                            with st.expander("📊 상세 결과 비교"):
                                detail_col1, detail_col2, detail_col3 = st.columns(3)
                                with detail_col1:
                                    st.metric("EasyOCR", results['easyocr_count'])
                                with detail_col2:
                                    st.metric("Tesseract", results['tesseract_count'])
                                with detail_col3:
                                    st.metric("최종 결합", results['combined_count'])
                                
                                # 각 엔진별 결과도 표시
                                if results['easyocr_only']:
                                    st.markdown("**EasyOCR 전용 결과:**")
                                    st.write(", ".join(results['easyocr_only']))
                                
                                if results['tesseract_only']:
                                    st.markdown("**Tesseract 전용 결과:**")
                                    st.write(", ".join(results['tesseract_only']))
                        
                        display_ingredients(results['combined'])
                    else:
                        st.warning("성분을 추출하지 못했습니다.")
                        
                elif ocr_engine_choice == "기본 EasyOCR (이전 버전)":
                    # 기존 방식 유지
                    with st.spinner("EasyOCR로 이미지에서 성분 분석 중...🔍"):
                        extracted_list = extract_ingredients_easyocr(image_array)
                    
                    end_time = time.time()
                    processing_time = end_time - start_time
                    
                    if extracted_list:
                        st.success(f"✅ 기본 EasyOCR로 {len(extracted_list)}개 성분 추출 완료! ({processing_time:.1f}초)")
                        display_ingredients(extracted_list)
                    else:
                        st.warning("성분을 추출하지 못했습니다.")
                        
                elif ocr_engine_choice == "기본 Tesseract (이전 버전)":
                    # 기존 방식 유지
                    with st.spinner("Tesseract OCR로 이미지에서 성분 분석 중...🔍"):
                        extracted_list = extract_ingredients_tesseract(image)
                    
                    end_time = time.time()
                    processing_time = end_time - start_time
                    
                    if extracted_list:
                        st.success(f"✅ 기본 Tesseract로 {len(extracted_list)}개 성분 추출 완료! ({processing_time:.1f}초)")
                        display_ingredients(extracted_list)
                    else:
                        st.warning("성분을 추출하지 못했습니다.")
                        
            except Exception as e:
                if progress_bar:
                    progress_bar.empty()
                if status_text:
                    status_text.empty()
                st.error(f"분석 중 오류가 발생했습니다: {e}")
                st.info("💡 다른 OCR 엔진을 시도해보세요.")



# 앱 실행 시 추가 정보
if uploaded_file is None:
    st.info("👆 왼쪽에서 성분표 이미지를 업로드해주세요.")
    
    # 샘플 이미지나 사용 예시를 보여줄 수 있음
    with st.expander("📖 사용법 가이드"):
        st.markdown("""
        ### 🎯 최적의 결과를 위한 팁
        
        1. **이미지 품질**
           - 300 DPI 이상의 고해상도 이미지 사용
           - 흐릿하지 않은 선명한 이미지
           
        2. **촬영 조건**  
           - 충분한 조명 확보
           - 그림자나 반사 최소화
           - 정면에서 수직으로 촬영
           
        3. **OCR 엔진 선택**
           - **결합 모드**: 가장 높은 정확도 (권장)
           - **향상된 EasyOCR**: 한글 인식에 강함
           - **향상된 Tesseract**: 영문 인식에 강함
           
        4. **후처리**
           - 결과를 검토하여 오인식된 내용 수정
           - 필요시 여러 엔진 결과 비교
        """)

st.markdown("---")
st.caption("🚀 Powered by Streamlit & Advanced OCR | EasyOCR & Tesseract")