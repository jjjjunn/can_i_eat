import os
from google.cloud import vision
from google.oauth2 import service_account
from dotenv import load_dotenv
import time
import re
import logging
from typing import List, Callable, Optional

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Google Cloud Vision API Key
# google_cloud_key_string = os.environ.get('GOOGLE_VISION')

# os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'google_cloud_vision.json'
# client_options = {'api_endpoint': 'eu-vision.googleaois.com'}
# client = vision.ImageAnnotatorClient(client_options = client_options)


class VisionTextExtractor:
    """
    Google Cloud Vision API를 사용하여 이미지에서 성분을 추출하고 관리하는 클래스
    """
    
    def __init__(self, api_endpoint: str = 'eu-vision.googleaois.com'):
        """
        VisionTextExtractor 클래스 초기화
        
        Args:
            api_endpoint(str): Google Cloud Vision API 엔드포인트 URL
        """
        self.api_endpoint = api_endpoint
        self.client = self._get_vision_client()
        
    # Google Cloud Vision API 클라이언트 초기화
    def _get_vision_client(self) -> vision.ImageAnnotatorClient:
        """
        Google Cloud Vision API 클라이언트를 생성하고 반환
        """
        try:
            # 환경변수에서 API 키 또는 서비스 계정 정보 가져오기
            # google_cloud_key = os.environ.get('GOOGLE_CLOUD_VISION')
            google_cloud_key = st.secret['GOOGLE_CREDENTIALS_JSON']['GOOGLE_CREDENTIALS_JSON']
            client_options = {'api_endpoint': self.api_endpoint}
            credentials = None
            
            if google_cloud_key:
                # JSON 키 파일 경로인 경우
                if google_cloud_key.endswith('.json') and os.path.exists(google_cloud_key):
                    credentials = service_account.Credentials.from_service_account_file(google_cloud_key)

            else:
                # 2) JSON 문자열일 수 있으므로 파싱 시도
                try:
                    json_obj = json.loads(google_cloud_key)
                    # 임시 파일로 JSON 저장
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
                        json.dump(json_obj, tmp_file)
                        tmp_path = tmp_file.name
                    credentials = service_account.Credentials.from_service_account_file(tmp_path)
                except json.JSONDecodeError:
                    # JSON이 아니면 무시(기존 코드처럼 None으로)
                    pass

            # credentaials 제공 시 credentaials 사용, 아닐 경우 client_options만 사용
            return vision.ImageAnnotatorClient(client_options=client_options, credentials=credentials)

        except Exception as e:
            logger.error(f"Google Vision API 클라이언트 초기화 실패: {e}")
            raise Exception(f"Google Vision API 설정을 확인해주세요: {e}")


    # 이미지 텍스트 감지 함수 (Google Cloud Vision API)
    def detect_text_from_image_google_vision(self, image_path: str) -> Optional[str]:
        """
        주어진 이미지에서 텍스트를 감지하여 반환 (Google Cloud Vision API 사용)
        
        Args:
            image_path(str): 분석할 이미지 파일 경로
            
        Returns:
            str: 이미지에서 감지된 전체 텍스트
            
        Raises:
            Exception: Google Cloud Vision API 호출 중 오류 발생
        """
        try:
            with open(image_path, 'rb') as image_file:
                content = image_file.read()
                
            image = vision.Image(content=content)
            
            # DOCUMENT_TEXT_DETECTION 을 사용하여 문서 구조를 포함한 텍스트 추출
            response = self.client.document_text_detection(image=image)
                      
            if response.error.message:
                raise Exception(
                    f'Google Vision API 오류: {response.error.message}\n'
                    '자세한 정보: https://cloud.google.com/apis/design/errors'
                )
            
            # 텍스트 추출
            if response.full_text_annotation:
                detected_text = response.full_text_annotation.text
                logger.info(f"텍스트 감지 성공: {len(detected_text)} 글자 추출")
                return detected_text
            else:
                logger.warning("이미지에서 텍스트를 찾을 수 없습니다.")
        
        except FileNotFoundError:
            raise Exception(f"이미지 파일을 찾을 수 없습니다: {image_path}")
        except Exception as e:
            logger.error(f"텍스트 감지 중 오류: {e}")
            raise Exception(f"Google Vision API 텍스트 감지 중 오류 발생: {e}")

    # 추출된 텍스트에서 성분 목록 파싱
    @staticmethod
    def parse_ingredients_from_text(text: str) -> List[str]:
        """
        추출된 텍스트에서 성분 목록 파싱
        
        Args:
            text(str) : OCR로 추출된 전체 텍스트
            
        Returns:
            List[str]: 파싱된 성분 목록
        """
        
        if not text or not text.strip():
            return []
        
        ingredients_list = []
        
        # 여러 언어의 성분 키워드 패턴
        ingredient_patterns = [
            # 한국어 패턴
            r'(성분|원재료명|원료|재료)\s*[:：]\s*(.+)',
            r'(성분|원재료명|원료|재료)\s*[:\s]*\n(.+)',
            
            # 영어 패턴
            r'(ingredients|contents|materials)\s*[:：]\s*(.+)',
            r'(ingredients|contents|materials)\s*[:\s]*\n(.+)',
            
            # 일반적인 콜론 뒤 패턴
            r'[:：]\s*(.+)',
        ]
        
        text_lower = text.lower()
        found_ingredients = False
        
        # 패턴 매칭 시도
        for pattern in ingredient_patterns:
            match = re.search(pattern, text_lower, re.DOTALL | re.IGNORECASE)
            if match:
                # 매칭된 그룹이 2개인 경우 (키워드 + 내용)
                if len(match.groups()) >= 2:
                    ingredients_text = match.group(2)
                else:
                    ingredients_text = match.group(1)
                    
                # 성분 텍스트를 줄 단위로 분리
                lines = [line.strip() for line in ingredients_text.split('\n') if line.strip()]
                
                # 각 줄을 쉼표나 세미콜론으로 추가 분리
                for line in lines:
                    # 쉼표, 세미콜론, 슬래시로 분리
                    parts = re.split(r'[,;/]', line)
                    for part in parts:
                        clean_part = part.strip()
                        if clean_part and len(clean_part) > 1:
                            ingredients_list.append(clean_part)
                
                found_ingredients = True
                break
            
            # 패턴으로 찾지 못한 경우, 전체 텍스트를 줄 단위로 분리하여 시도
            if not found_ingredients:
                logger.info("키워드 패턴을 찾지 못해 전체 텍스트를 분석합니다")
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                
                for line in lines:
                    # 너무 긴 줄이나 특정 패턴을 제외
                    if len(line) > 100 or any(keyword in line.lower() for keyword in ['제조', '유통', '보관', '주의', 'tel', 'fax', 'www']):
                        continue
                    
                    # 쉼표로 분리된 여러 성분이 한 줄에 있을 수 있음
                    parts = re.split(r'[,;]', line)
                    for part in parts:
                        clean_part = part.strip()
                        if clean_part and len(clean_part) > 1:
                            ingredients_list.append(clean_part)
            
            return ingredients_list

    # 성분 목록 정리 후 불필요한 항목 제거하는 함수
    @staticmethod
    def clean_and_filter_ingredients(ingredients_list: List[str]) -> List[str]:
        """
        성분 목록을 정리하고 불필요한 항목 제거
        
        Args:
            ingredients_list (List[str]): 원본 성분 목록
            
        Returns:
            List[str]: 정리된 성분 목록
        """
        
        if not ingredients_list:
            return []
        
        cleaned = []
        
        # 제외할 키워드들
        exclude_keywords = [
            # 한국어
            '영양정보', '성분', '원재료명', '원료', '재료', '함량', '제조일자', '유통기한',
            '보관방법', '주의사항', '제조회사', '판매회사', '수입회사', '고객센터',
            '제조', '유통', '보관', '주의', '회사', '전화', '팩스', '이메일', '홈페이지',
            
            # 영어
            'ingredients', 'contents', 'materials', 'nutrition', 'facts', 'information',
            'manufactured', 'distributed', 'storage', 'caution', 'warning', 'company',
            'tel', 'fax', 'email', 'website', 'www', 'http',
            
            # 기타
            '(주)', 'co.', 'ltd', 'inc', 'corp'
        ]
        
        for ingredient in ingredients_list:
            # 기본 정리
            cleaned_ingredient = ingredient.strip()
            
            # 빈문자열이나 너무 짧은 것 제외
            if not cleaned_ingredient or len(cleaned_ingredient) <= 1:
                continue
            
            # 숫자만 있는 것 제외
            if cleaned_ingredient.isdigit():
                continue
            
            # 특수문자만 있는 것 제외
            if re.match(r'^[^\w\s가-힣]+$', cleaned_ingredient):
                continue
            
            # 제외 키워드 체크 (대소문자 구분 없이)
            if any(keyword in cleaned_ingredient.lower() for keyword in exclude_keywords):
                continue
            
            # 괄호만 있는 내용 제외
            if re.match(r'^\([^)]*\)$', cleaned_ingredient):
                continue
            
            # 너무 긴 텍스트 제외 (일반적으로 성분명은 50자를 넘지 않음)
            if len(cleaned_ingredient) > 50:
                continue
            
            # URL이나 이메일 패턴 제외
            if re.search(r'[@.]', cleaned_ingredient) and ('.' in cleaned_ingredient or '@' in cleaned_ingredient):
                continue
            
            cleaned.append(cleaned_ingredient)
            
        # 중복 제거하면서 순서 유지
        seen = set()
        result = []
        for item in cleaned:
            if item not in seen:
                seen.add(item)
                result.append(item)
                
        return result

    def get_text_confidence_score(self, image_path: str) -> float:
            """
            이미지의 텍스트 인식 신뢰도 점수를 반환
            
            Args:
                image_path (str): 이미지 파일 경로
                
            Returns:
                float: 평균 신뢰도 점수 (0.0 ~ 1.0)
            """
            try:
                with open(image_path, 'rb') as image_file:
                    content = image_file.read()
                    
                image = vision.Image(content=content)
                response = self.client.document_text_detection(image=image)
                
                if not response.full_text_annotation:
                    return 0.0
                
                confidences = []
                for page in response.full_text_annotation.pages:
                    for block in page.blocks:
                        confidences.append(block.confidence)
                
                return sum(confidences) / len(confidences) if confidences else 0.0
            
            except Exception as e:
                logger.error(f"신뢰도 점수 계산 중 오류: {e}")
                return 0.0

    def suggest_image_improvements(self, image_path: str) -> List[str]:
        """
        이미지 품질 개선을 위한 제안사항을 반환
        
        Args:
            image_path (str): 이미지 파일 경로
            
        Returns:
            List[str]: 개선 제안사항 목록
        """
        suggestions = []
        
        try:
            from PIL import Image
            
            with Image.open(image_path) as img:
                width, height = img.size
                
                # 해상도 체크
                if max(width, height) < 800:
                    suggestions.append("더 높은 해상도의 이미지를 사용해보세요 (800px 이상 권장)")
                
                # 파일 크기 체크
                file_size = os.path.getsize(image_path) / 1024  # KB
                if file_size < 100:
                    suggestions.append("이미지 파일 크기가 작습니다. 더 선명한 이미지를 사용해보세요")
                
                # 종횡비 체크
                aspect_ratio = width / height
                if aspect_ratio > 3 or aspect_ratio < 0.33:
                    suggestions.append("이미지의 가로세로 비율이 극단적입니다. 정사각형에 가까운 비율이 좋습니다")
        
        except Exception as e:
            logger.error(f"이미지 분석 중 오류: {e}")
            suggestions.append("이미지 파일을 확인해주세요")
        
        # 신뢰도 기반 제안
        confidence = self.get_text_confidence_score(image_path)
        if confidence < 0.7:
            suggestions.extend([
                "이미지가 흐릿하거나 글자가 불분명할 수 있습니다",
                "조명이 좋은 곳에서 다시 촬영해보세요",
                "카메라 흔들림 없이 정면에서 촬영해보세요"
            ])
        
        return suggestions[:5]  # 최대 5개 제안만 반환

    # 성분 추출 및 진행 상황 관리 함수
    def extract_ingredients_with_progress(
        self,
        image_path: str,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> List[str]:
        """
        Google Cloud Vision API를 사용하여 이미지에서 텍스트를 추출하고 성분을 파싱하며,
        진행 상황을 콜백 함수로 업데이트
        
        Args:
            image_path (str): 분석할 이미지 파일 경로
            progress_callback (Optional[Callable[[int, str], None]]): 진행 상황을 업데이트하는 콜백 함수
                progress_callback(value, message)
                value: 0-100 범위의 정수, message는 상태 메시지
                
        Returns:
        List[str]: 추출된 성분 목록
            
        Raises:
            Exception: 텍스트 감지 또는 성분 추출 중 오류 발생
        """

        def update_progress(value: int, message: str):
            """진행 상황 업데이트 헬퍼 함수"""
            if progress_callback:
                progress_callback(value, message)
            logger.info(f"진행률: {value}% - {message}")    
            
        try:
            update_progress(0, "OCR 분석 시작 중...")
            time.sleep(0.1) # UI 업데이트를 위한 짧은 대기
            
            # 1단계: 이미지 파일 존재 확인
            if not os.path.exists(image_path):
                raise Exception(f"이미지 파일을 찾을 수 없습니다: {image_path}")
            
            update_progress(10, "이미지 파일 확인 완료...")

            # 2단계: Google Vision API로 텍스트 감지
            update_progress(20, "Google Vision API 호출 중...")
            
            full_text = self.detect_text_from_image_google_vision(image_path)
            
            if not full_text or not full_text.strip():
                update_progress(100, "텍스트를 찾을 수 없음")
                logger.warning("이미지에서 텍스트를 추출하지 못했습니다")
                return []
            
            update_progress(60, "텍스트 감지 완료, 성분 파싱 중...")
            
            # 3단계: 텍스트에서 성분 파싱
            raw_ingredients = self.parse_ingredients_from_text(full_text)
            
            update_progress(80, "성분 목록 정리 중...")
            
            # 4단계: 성분 목록 정리 및 필터링
            cleaned_ingredients = self.clean_and_filter_ingredients(raw_ingredients)
            
            update_progress(100, f"성분 분석 완료! ({len(cleaned_ingredients)}개 추출)")
            
            logger.info(f"성분 추출 완료: {len(cleaned_ingredients)}개 성분")
            
            return cleaned_ingredients

        except Exception as e:
            update_progress(100, "오류 발생")
            logger.error(f"성분 추출 중 오류: {e}")
            raise Exception(f"성분 추출 중 오류 발생: {e}")


    # 여러 이미지에서 성분을 일괄 추출하는 함수
    def batch_extract_ingredients(
        self,
        image_paths: List[str],
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> List[dict]:
        """
        여러 이미지에서 성분을 일괄 추출
        
        Args:
            image_paths (List[str]): 분석할 이미지 파일 경로 목록
            progress_callback (Optional[Callable[[int, str], None]]): 진행 상황 콜백
            
        Returns:
            List[dict]: 각 이미지별 추출 결과
                [{"image_path": str, "ingredients": List[str], "success": bool, "error": str}]
        """
        results = []
        total_images = len(image_paths)
        
        for i, image_path in enumerate(image_paths):
            try:
                if progress_callback:
                    progress_callback(
                        int((i / total_images) * 100), 
                        f"이미지 {i+1}/{total_images} 처리 중..."
                    )
                
                ingredients = self.extract_ingredients_with_progress(image_path)
                
                results.append({
                    "image_path": image_path,
                    "ingredients": ingredients,
                    "success": True,
                    "error": None
                })
                
            except Exception as e:
                results.append({
                    "image_path": image_path,
                    "ingredients": [],
                    "success": False,
                    "error": str(e)
                })
        
        if progress_callback:
            progress_callback(100, f"일괄 처리 완료 ({total_images}개 이미지)")
        
        return results

    # Google Cloud Vision API 연결 상태 확인 함수
    def validate_api_connection(self) -> dict:
        """
        Google Vision API 연결 상태를 확인
        
        Returns:
            dict: 연결 상태 정보
                {"connected": bool, "message": str, "error": Optional[str]}
        """
        try:
            # 간단한 테스트 이미지 생성 (1x1 픽셀 PNG)
            test_image_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x0f\x00\x00\x01\x00\x01\x00\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
            
            image = vision.Image(content=test_image_data)
            response = self.client.text_detection(image=image)
            
            if response.error.message:
                return {
                    "connected": False,
                    "message": "API 호출 실패",
                    "error": response.error.message
                }
            
            return {
                "connected": True,
                "message": "Google Vision API 연결 성공",
                "error": None
            }
            
        except Exception as e:
            return {
                "connected": False,
                "message": "API 연결 실패",
                "error": str(e)
            }


    # 성분 추출 및 진행 상황 관리 함수 (기존)
    # def extract_ingredients_with_progress(image_path, progress_callback):
    #     """
    #     Google Cloud Vision API 사용하여 이미지에서 텍스트를 추출하고 성분을 파싱하며,
    #     진행 상황을 콜백 함수로 업데이트
        
    #     Args:
    #         image_path(str): 분석할 이미지 파일 경로
    #         progress_callback (callable): 진행 상황을 업데이트하는 콜백 함수
    #             progress_callback(value, message)
    #             value: 0-100 범위의 정수, message는 상태 메시지
        
    #     Returns:
    #         list: 추출된 성분 목록
            
    #     Raises:
    #         Exception: 텍스트 감지 또는 성분 추출 중 오류 발생
    #     """
        
    #     progress_callback(0, "OCR 분석 시작 중...")
        
    #     try:
    #         # 텍스트 감지 함수 호출
    #         full_text = detect_text_from_image_google_vision(image_path)
            
    #         progress_callback(70, "텍스트 감지 완료, 성분 파싱 중...")
            
    #         # 성분 파싱 로직
    #         ingredients_list = []
            
    #         # 1. "성분" 또는 "Ingredients" 와 같은 키워드 뒤의 내용 파싱
    #         # 한국어와 영어 모두 고려
    #         match = re.search(r'(성분|Ingredients|원재료명|영양정보)\s*(.+)', full_text, re.DO)
    #         if match:
    #             # 키워드 뒤의 모든 텍스트를 가져와서 줄 단위로 분리
    #             raw_ingredients_text = match.group(2)
    #             temp_list = [line.strip() for line in raw_ingredients_text.split('\n') if line.strip()]
                
    #             # 불필요한 문장 제거
    #             ingredients_list.extend(temp_list)
                
    #         else:
    #             # 키워드 찾지 못할 경우 전체 텍스트를 줄 단위로 분리하여 시도
    #             ingredients_list = [line.strip() for line in full_text.split('\n') if line.strip()]
                
    #         # 중복 제거
    #         ingredients_list = list(dict.fromkeys(ingredients_list))
            
    #         progress_callback(100, "성분 분석 완료!")
            
    #         return ingredients_list
        
    #     except Exception as e:
    #         progress_callback(100, "오류 발생")
    #         raise Exception(f"성분 추출 중 오류 발생: {e}")
        

    # # 성분 목록 정리 함수(기존)
    # def clean_ingredients_list(ingredients_list):
    #     if not ingredients_list:
    #         return []
            
    #     cleaned = []
    #     for ingredient in ingredients_list:
    #         # 특수 문자 정리 및 공백 제거
    #         cleaned_ingredient = ingredient.strip()
            
    #         # 너무 짧거나 의미없는 텍스트 제거 (1글자 또는 숫자)
    #         if len(cleaned_ingredient) <= 1 or cleaned_ingredient.isdigit():
    #             continue
            
    #         # 일반적인 노이즈 텍스트 제거
    #         noise_patterns = ['영양정보', '성분', 'ingredients', '원재료명', '함량', '제조일자']
    #         if any(pattern in cleaned_ingredient.lower() for pattern in noise_patterns):
    #             continue
            
    #         # 괄호 안의 내용만 있는 경우 제거
    #         if cleaned_ingredient.startswith('(') and cleaned_ingredient.endswith(')'):
    #             continue
            
    #         cleaned.append(cleaned_ingredient)
            
    #     # 중복 제거하면서 순서 유지
    #     seen = set()
    #     result = []
    #     for item in cleaned:
    #         if item not in seen:
    #             seen.add(item)
    #             result.append(item)


    #     return result
