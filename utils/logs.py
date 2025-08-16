import requests
import logging
from datetime import datetime
import json
import streamlit as st
from pathlib import Path
import os
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class UserLogsViewer:
    """사용자 음식 분석 기록을 조회/삭제하는 공용 클라이언트"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def _build_headers(self, user_id: Optional[str] = None, auth_token: Optional[str] = None) -> Dict[str, str]:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if user_id:
            headers["X-User-Id"] = str(user_id)
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        return headers

    def get_user_logs(self, user_id: str, limit: int = 20, offset: int = 0, auth_token: Optional[str] = None) -> Dict[str, Any]:
        """사용자의 음식 분석 기록 조회"""
        url = f"{self.base_url}/users/{user_id}/logs/"
        params = {"limit": limit, "offset": offset}
        headers = self._build_headers(user_id=user_id, auth_token=auth_token)

        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"get_user_logs 실패: {e}")
            return {"error": str(e), "status_code": getattr(e.response, "status_code", None)}

    def delete_log(self, user_id: str, log_id: str, auth_token: Optional[str] = None) -> Dict[str, Any]:
        """특정 기록 삭제"""
        url = f"{self.base_url}/users/{user_id}/logs/{log_id}/"
        headers = self._build_headers(user_id=user_id, auth_token=auth_token)

        try:
            response = requests.delete(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"delete_log 실패: {e}")
            return {"error": str(e), "status_code": getattr(e.response, "status_code", None)}

    def delete_all_logs(self, user_id: str, auth_token: Optional[str] = None) -> Dict[str, Any]:
        """모든 기록 삭제"""
        url = f"{self.base_url}/users/{user_id}/logs/"
        headers = self._build_headers(user_id=user_id, auth_token=auth_token)

        try:
            response = requests.delete(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"delete_all_logs 실패: {e}")
            return {"error": str(e), "status_code": getattr(e.response, "status_code", None)}


def format_datetime(dt_str: str) -> str:
    """ISO 형식의 날짜를 읽기 쉬운 형식으로 변환"""
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return dt_str


def display_log_detail(log: Dict[str, Any]) -> Optional[str]:
    """개별 로그의 상세 정보 표시. 삭제 버튼 클릭 시 log_id 반환"""
    with st.expander(f"📝 기록 ID: {log['id']}", expanded=False):
        col1, col2 = st.columns([1, 2])

        with col1:
            # 디버그 정보 추가
            st.write("**디버그 정보:**")
            st.write(f"image_url: {log.get('image_url', 'None')}")
            st.write(f"image_url type: {type(log.get('image_url'))}")
            
            # 이미지 파일 존재 여부 확인
            image_url = log.get('image_url')
            if image_url:
                file_exists = check_image_file_exists(image_url)
                st.write(f"이미지 파일 존재: {file_exists}")
            
            if log.get("image_url"):
                # 저장된 이미지 경로인 경우
                if log["image_url"].startswith("uploads/"):
                    # FastAPI 정적 파일 URL로 변환 (절대 URL 사용)
                    api_url = os.getenv("API_URL", "http://localhost:8000")
                    image_url = f"{api_url.rstrip('/')}/static/{log['image_url']}"
                    st.write(f"변환된 URL: {image_url}")
                    
                    # 파일 존재 여부 확인
                    if check_image_file_exists(log["image_url"]):
                        try:
                            st.image(image_url, caption="업로드된 이미지", width=300)
                        except Exception as e:
                            st.error(f"이미지 로드 실패: {e}")
                            # 로컬 파일로 직접 표시 시도
                            try:
                                local_path = Path.cwd() / log["image_url"]
                                st.image(str(local_path), caption="업로드된 이미지 (로컬)", width=300)
                            except Exception as e2:
                                st.error(f"로컬 이미지 로드도 실패: {e2}")
                    else:
                        st.error("이미지 파일이 존재하지 않습니다")
                else:
                    # 외부 URL인 경우
                    try:
                        st.image(log["image_url"], caption="업로드된 이미지", width=300)
                    except Exception as e:
                        st.error(f"이미지 로드 실패: {e}")
            else:
                st.info("이미지가 없습니다")

        with col2:
            st.write("**생성 시간:**", format_datetime(log["created_at"]))

            if log.get("ocr_result"):
                st.write("**OCR 결과:**")
                try:
                    ocr_text = json.dumps(log["ocr_result"], ensure_ascii=False, indent=2) if not isinstance(log["ocr_result"], str) else log["ocr_result"]
                except Exception:
                    ocr_text = str(log["ocr_result"])  # 안전하게 문자열화
                st.text_area("OCR 결과 내용", value=ocr_text, height=120, key=f"ocr_{log['id']}")

            if log.get("gemini_response"):
                st.write("**AI 분석 결과:**")
                try:
                    if isinstance(log["gemini_response"], str):
                        gemini_data = json.loads(log["gemini_response"])  # 문자열 JSON인 경우 파싱
                        st.json(gemini_data)
                    else:
                        st.json(log["gemini_response"])  # 이미 dict인 경우
                except Exception:
                    st.text_area("AI 분석 결과 내용", value=str(log["gemini_response"]), height=150, key=f"gemini_{log['id']}")

        if st.button(f"🗑️ 이 기록 삭제", key=f"delete_{log['id']}", type="secondary"):
            logger.info(f"기록 삭제 버튼 클릭: log_id={log['id']}")
            return log["id"]

    return None


def check_image_file_exists(image_path: str) -> bool:
    """이미지 파일이 실제로 존재하는지 확인"""
    if not image_path:
        return False
    
    try:
        # 상대 경로를 절대 경로로 변환
        if image_path.startswith("uploads/"):
            absolute_path = Path.cwd() / image_path
            exists = absolute_path.exists()
            logger.info(f"이미지 파일 확인: {absolute_path} - 존재: {exists}")
            return exists
        return False
    except Exception as e:
        logger.error(f"이미지 파일 확인 중 오류: {e}")
        return False


