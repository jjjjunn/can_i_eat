import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import json
from typing import Optional, List, Dict, Any
import uuid
import os

# .env 파일에서 환경 변수 로드
from dotenv import load_dotenv
load_dotenv()

from utils.logs import UserLogsViewer, format_datetime, display_log_detail

# 설정
API_BASE_URL = os.getenv("API_URL")  # FastAPI 서버 주소

## 상세 표시/시간 포맷은 utils.logs의 공용 함수 사용

def main():
    st.set_page_config(
        page_title="사용자 음식 분석 기록 조회",
        page_icon="🍽️",
        layout="wide"
    )
    
    st.title("🍽️ 사용자 음식 분석 기록 조회")
    st.markdown("---")
    
    # 초기화
    if 'logs_viewer' not in st.session_state:
        st.session_state.logs_viewer = UserLogsViewer(API_BASE_URL)
    if 'current_logs' not in st.session_state:
        st.session_state.current_logs = []
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 0
    
    # 사이드바 설정
    with st.sidebar:
        st.header("🔧 설정")
        
        # API 서버 주소 설정
        api_url = st.text_input("API 서버 주소", value=API_BASE_URL)
        if api_url != API_BASE_URL:
            st.session_state.logs_viewer = UserLogsViewer(api_url)
        
        # 사용자 ID 입력
        user_id = st.text_input("사용자 ID", help="조회할 사용자의 UUID를 입력하세요")
        
        # 인증 토큰 (선택사항)
        auth_token = st.text_input("인증 토큰 (선택사항)", type="password", help="Bearer 토큰이 필요한 경우 입력하세요")
        
        # 페이지 설정
        st.subheader("📄 페이지 설정")
        page_size = st.slider("한 페이지당 기록 수", min_value=1, max_value=50, value=10)
        
        # 새로고침 버튼
        if st.button("🔄 새로고침", type="primary"):
            st.session_state.current_page = 0
            st.rerun()
    
    # 메인 영역
    if not user_id:
        st.info("👈 사이드바에서 사용자 ID를 입력하세요.")
        return
    
    try:
        # UUID 검증
        uuid.UUID(user_id)
    except ValueError:
        st.error("올바른 UUID 형식의 사용자 ID를 입력하세요.")
        return
    
    # 기록 조회
    offset = st.session_state.current_page * page_size
    result = st.session_state.logs_viewer.get_user_logs(
        user_id=user_id,
        limit=page_size,
        offset=offset,
        auth_token=auth_token if auth_token else None
    )
    
    if 'error' in result:
        st.error(f"오류 발생: {result['error']}")
        if result.get('status_code') == 403:
            st.warning("접근 권한이 없습니다. 올바른 사용자 ID와 인증 토큰을 확인하세요.")
        elif result.get('status_code') == 404:
            st.info("조회할 기록이 없습니다.")
        return
    
    # 결과 표시
    logs = result.get('logs', [])
    message = result.get('message', '')
    
    if not logs:
        st.info("조회할 기록이 없습니다.")
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
            delete_result = st.session_state.logs_viewer.delete_all_logs(user_id, auth_token if auth_token else None)
            if 'error' in delete_result:
                st.error(f"삭제 실패: {delete_result['error']}")
            else:
                st.success(delete_result.get('message', '모든 기록이 삭제되었습니다'))
                st.rerun()
    
    st.markdown("---")
    
    # 기록 목록 표시
    delete_log_id = None
    for log in logs:
        log_to_delete = display_log_detail(log)
        if log_to_delete:
            delete_log_id = log_to_delete
    
    # 개별 기록 삭제 처리
    if delete_log_id:
        with st.spinner("기록을 삭제하는 중..."):
            delete_result = st.session_state.logs_viewer.delete_log(user_id, delete_log_id, auth_token if auth_token else None)
            if 'error' in delete_result:
                st.error(f"삭제 실패: {delete_result['error']}")
            else:
                st.success(delete_result.get('message', '기록이 삭제되었습니다'))
                st.rerun()
    
    # 페이지네이션
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
    
    # 데이터 요약 표시
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