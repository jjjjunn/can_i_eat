import streamlit as st
import os
from google.oauth2 import service_account
from google.auth import default
import json

def get_google_credentials():
    """Google Cloud 인증 정보 반환"""
    try:
        # Streamlit Cloud에서 실행 중인 경우
        if hasattr(st, 'secrets') and 'OOGLE_CREDENTIALS_JSON' in st.secrets:
            credentials_json = st.secrets["OOGLE_CREDENTIALS_JSON"]
            credentials = service_account.Credentials.from_service_account_info(
                credentials_json,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
            return credentials
        
        # 로컬 환경에서 서비스 계정 키 파일 사용
        elif os.path.exists('google_cloud_vision.json'):
            credentials = service_account.Credentials.from_service_account_file(
                'google_cloud_visuon.json',
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
            return credentials
        
        # 기본 인증 시도 (로컬 gcloud 설정 등)
        else:
            credentials, project = default()
            return credentials
            
    except Exception as e:
        st.error(f"Google Cloud 인증 실패: {e}")
        return None

def get_api_key():
    """Google API 키 반환"""
    try:
        # Streamlit Cloud secrets 확인
        if hasattr(st, 'secrets') and 'GOOGLE_API_KEY' in st.secrets:
            return st.secrets["GOOGLE_API_KEY"]
        
        # 환경변수 확인
        elif os.getenv('GOOGLE_API_KEY'):
            return os.getenv('GOOGLE_API_KEY')
        
        else:
            st.error("Google API 키가 설정되지 않았습니다.")
            return None
            
    except Exception as e:
        st.error(f"API 키 가져오기 실패: {e}")
        return None
