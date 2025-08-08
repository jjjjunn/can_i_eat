import easyocr
import pytesseract
from PIL import Image, ImageEnhance
import numpy as np
import re
from typing import Union
import cv2

class AdvancedOCRProcessor:
    def __init__(self):
        # EasyOCR Reader는 외부에서 주입받도록 수정 (Streamlit 캐싱 때문)
        self.easyocr_reader = None
    
    def set_easyocr_reader(self, reader):
        """EasyOCR Reader 설정 (Streamlit 캐싱된 객체 사용)"""
        self.easyocr_reader = reader
    
    def enhance_image_quality(self, image_array: np.ndarray) -> np.ndarray:
        """이미지 품질 향상을 위한 고급 전처리"""
        # PIL Image로 변환하여 향상 필터 적용
        pil_image = Image.fromarray(image_array)
        
        # 1. 선명도 향상
        sharpness_enhancer = ImageEnhance.Sharpness(pil_image)
        enhanced_image = sharpness_enhancer.enhance(2.0)
        
        # 2. 대비 향상
        contrast_enhancer = ImageEnhance.Contrast(enhanced_image)
        enhanced_image = contrast_enhancer.enhance(1.5)
        
        # 3. 밝기 조정
        brightness_enhancer = ImageEnhance.Brightness(enhanced_image)
        enhanced_image = brightness_enhancer.enhance(1.2)
        
        return np.array(enhanced_image)
    
    def advanced_preprocess_image(self, image_array: np.ndarray) -> list[np.ndarray]:
        """다양한 전처리 버전을 생성하여 OCR 성능 향상"""
        processed_images = []
        
        # 이미지 품질 향상 먼저 적용
        enhanced_image = self.enhance_image_quality(image_array)
        
        # 그레이스케일 변환
        if len(enhanced_image.shape) == 3:
            gray = cv2.cvtColor(enhanced_image, cv2.COLOR_RGB2GRAY)
        else:
            gray = enhanced_image.copy()
        
        # 버전 1: 기본 적응형 이진화
        blurred1 = cv2.GaussianBlur(gray, (3, 3), 0)
        thresh1 = cv2.adaptiveThreshold(blurred1, 255,
                                       cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY, 11, 2)
        processed_images.append(thresh1)
        
        # 버전 2: OTSU 이진화
        blurred2 = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh2 = cv2.threshold(blurred2, 0, 255, 
                                  cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        processed_images.append(thresh2)
        
        # 버전 3: 모폴로지 연산 강화
        thresh3 = thresh1.copy()
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        thresh3 = cv2.morphologyEx(thresh3, cv2.MORPH_CLOSE, kernel)
        thresh3 = cv2.morphologyEx(thresh3, cv2.MORPH_OPEN, kernel)
        processed_images.append(thresh3)
        
        # 버전 4: 히스토그램 평활화 + 적응형 이진화
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced_gray = clahe.apply(gray)
        blurred4 = cv2.GaussianBlur(enhanced_gray, (3, 3), 0)
        thresh4 = cv2.adaptiveThreshold(blurred4, 255,
                                       cv2.ADAPTIVE_THRESH_MEAN_C,
                                       cv2.THRESH_BINARY, 15, 3)
        processed_images.append(thresh4)
        
        # 버전 5: 원본 그레이스케일
        processed_images.append(gray)
        
        return processed_images
    
    def extract_ingredients_from_line(self, line: str) -> list[str]:
        """텍스트 라인에서 성분 추출 (개선된 버전)"""
        if not line or not isinstance(line, str):
            return []
        
        line = line.strip()
        
        # 건너뛸 패턴들 (더 포괄적)
        skip_patterns = [
            r'성분.*정보', r'영양.*정보', r'ingredients', r'nutrition',
            r'함량', r'칼로리', r'kcal', r'mg', r'g\b', r'ml', r'%',
            r'유통기한', r'제조일', r'원산지', r'보관방법',
            r'^\d+$', r'^[0-9.,]+$'  # 숫자만 있는 라인
        ]
        
        for pattern in skip_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                return []
        
        # 길이 체크
        if len(line) < 2 or len(line) > 100:
            return []
        
        # 성분 분리 (더 정교한 구분자)
        split_pattern = re.compile(r'[,./\(\)\[\]\{\}\+\-\s]+')
        split_items = split_pattern.split(line)
        
        ingredients = []
        for item in split_items:
            cleaned_item = self.clean_ingredient_name(item)
            if cleaned_item:
                ingredients.append(cleaned_item)
        
        return ingredients
    
    def clean_ingredient_name(self, item: str) -> str:
        """개별 성분명 정제"""
        if not item:
            return ""
        
        # 앞뒤 공백 및 특수문자 제거
        cleaned = re.sub(r'^[^\w가-힣]+|[^\w가-힣]+$', '', item.strip())
        
        # 너무 짧거나 숫자만 있는 경우 제외
        if len(cleaned) < 2 or cleaned.isdigit():
            return ""
        
        # 의미없는 단어 제외
        meaningless_words = [
            '등', '기타', '및', '또는', '포함', '함유', '첨가',
            'etc', 'and', 'or', 'contains', 'includes'
        ]
        
        if cleaned.lower() in meaningless_words:
            return ""
        
        return cleaned
    
    def post_process_ingredients(self, ingredients: list[str]) -> list[str]:
        """최종 성분 목록 후처리"""
        # 중복 제거 (대소문자 구분 없이)
        unique_ingredients = []
        seen_lower = set()
        
        for ingredient in ingredients:
            if ingredient and ingredient.lower() not in seen_lower:
                unique_ingredients.append(ingredient)
                seen_lower.add(ingredient.lower())
        
        # 길이순 정렬 (짧은 것부터)
        unique_ingredients.sort(key=len)
        
        # 최대 20개까지
        return unique_ingredients[:20]

# 전역 프로세서 인스턴스
_processor = AdvancedOCRProcessor()

def set_processor_reader(reader):
    """프로세서에 EasyOCR Reader 설정"""
    _processor.set_easyocr_reader(reader)

# 기존 함수들 (향상된 버전)
def extract_ingredients_easyocr(image_array: np.ndarray) -> list[str]:
    """
    EasyOCR을 사용한 성분 추출 (향상된 버전)
    """
    if _processor.easyocr_reader is None:
        # 캐싱되지 않은 경우 임시로 생성
        reader = easyocr.Reader(['ko', 'en'], gpu=False)
        _processor.set_easyocr_reader(reader)
    
    processed_images = _processor.advanced_preprocess_image(image_array)
    
    all_ingredients = []
    for processed_img in processed_images:
        try:
            result = _processor.easyocr_reader.readtext(processed_img, detail=0)
            for line in result:
                ingredients = _processor.extract_ingredients_from_line(line)
                all_ingredients.extend(ingredients)
        except Exception as e:
            print(f"EasyOCR 처리 중 오류: {e}")
    
    return _processor.post_process_ingredients(all_ingredients)

def extract_ingredients_tesseract(image_input: Union[str, Image.Image, np.ndarray]) -> list[str]:
    """
    Tesseract OCR을 사용한 성분 추출 (향상된 버전)
    """
    # 입력을 numpy 배열로 변환
    image_array = None
    if isinstance(image_input, str):
        try:
            pil_image = Image.open(image_input)
            image_array = np.array(pil_image)
        except Exception as e:
            print(f"파일 로드 오류: {e}")
            return []
    elif isinstance(image_input, Image.Image):
        image_array = np.array(image_input)
    elif isinstance(image_input, np.ndarray):
        image_array = image_input
    else:
        print("지원되지 않는 입력 형식")
        return []
    
    processed_images = _processor.advanced_preprocess_image(image_array)
    
    all_ingredients = []
    for processed_img in processed_images:
        pil_img = Image.fromarray(processed_img)
        
        # 다양한 Tesseract 설정 시도
        configs = [
            '--psm 6 -c tessedit_char_whitelist=0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ가-힣().,/+[]{}% ',
            '--psm 8 -c tessedit_char_whitelist=0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ가-힣().,/+[]{}% ',
            '--psm 13'
        ]
        
        for config in configs:
            try:
                result_text = pytesseract.image_to_string(pil_img, lang='kor+eng', config=config)
                lines = result_text.split('\n')
                
                for line in lines:
                    ingredients = _processor.extract_ingredients_from_line(line)
                    all_ingredients.extend(ingredients)
                    
            except Exception as e:
                print(f"Tesseract 설정 '{config}' 처리 중 오류: {e}")
    
    return _processor.post_process_ingredients(all_ingredients)

# 새로운 고급 함수들
def extract_ingredients_advanced(image_array: np.ndarray) -> list[str]:
    """
    EasyOCR과 Tesseract를 결합한 고급 성분 추출
    """
    easyocr_ingredients = extract_ingredients_easyocr(image_array)
    tesseract_ingredients = extract_ingredients_tesseract(image_array)
    
    # 두 결과를 합치고 후처리
    combined_ingredients = easyocr_ingredients + tesseract_ingredients
    return _processor.post_process_ingredients(combined_ingredients)

def extract_ingredients_with_confidence(image_array: np.ndarray) -> dict:
    """
    신뢰도 정보와 함께 성분 추출
    """
    easyocr_ingredients = extract_ingredients_easyocr(image_array)
    tesseract_ingredients = extract_ingredients_tesseract(image_array)
    combined_ingredients = _processor.post_process_ingredients(
        easyocr_ingredients + tesseract_ingredients
    )
    
    return {
        'combined': combined_ingredients,
        'easyocr_only': easyocr_ingredients,
        'tesseract_only': tesseract_ingredients,
        'easyocr_count': len(easyocr_ingredients),
        'tesseract_count': len(tesseract_ingredients),
        'combined_count': len(combined_ingredients),
        'confidence_score': len(combined_ingredients) / max(1, len(set(combined_ingredients)))
    }

# 진행률 표시가 있는 버전 (Streamlit용)
def extract_ingredients_easyocr_with_progress(image_array: np.ndarray, progress_callback=None) -> list[str]:
    """진행률 콜백이 있는 EasyOCR 버전"""
    if _processor.easyocr_reader is None:
        reader = easyocr.Reader(['ko', 'en'], gpu=False)
        _processor.set_easyocr_reader(reader)
    
    if progress_callback:
        progress_callback(0.2, "이미지 전처리 중...")
    
    processed_images = _processor.advanced_preprocess_image(image_array)
    
    all_ingredients = []
    total_images = len(processed_images)
    
    for i, processed_img in enumerate(processed_images):
        if progress_callback:
            progress = 0.2 + (0.6 * (i + 1) / total_images)
            progress_callback(progress, f"EasyOCR 처리 중... ({i+1}/{total_images})")
        
        try:
            result = _processor.easyocr_reader.readtext(processed_img, detail=0)
            for line in result:
                ingredients = _processor.extract_ingredients_from_line(line)
                all_ingredients.extend(ingredients)
        except Exception as e:
            print(f"EasyOCR 처리 중 오류: {e}")
    
    if progress_callback:
        progress_callback(0.9, "결과 정제 중...")
    
    final_ingredients = _processor.post_process_ingredients(all_ingredients)
    
    if progress_callback:
        progress_callback(1.0, "완료!")
    
    return final_ingredients

def extract_ingredients_tesseract_with_progress(image_array: np.ndarray, progress_callback=None) -> list[str]:
    """진행률 콜백이 있는 Tesseract 버전"""
    if progress_callback:
        progress_callback(0.2, "이미지 전처리 중...")
    
    processed_images = _processor.advanced_preprocess_image(image_array)
    
    all_ingredients = []
    total_processes = len(processed_images) * 3
    current_process = 0
    
    for processed_img in processed_images:
        pil_img = Image.fromarray(processed_img)
        
        configs = [
            ('PSM 6', '--psm 6 -c tessedit_char_whitelist=0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ가-힣().,/+[]{}% '),
            ('PSM 8', '--psm 8 -c tessedit_char_whitelist=0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ가-힣().,/+[]{}% '),
            ('PSM 13', '--psm 13')
        ]
        
        for config_name, config in configs:
            current_process += 1
            if progress_callback:
                progress = 0.2 + (0.6 * current_process / total_processes)
                progress_callback(progress, f"Tesseract {config_name} 처리 중...")
            
            try:
                result_text = pytesseract.image_to_string(pil_img, lang='kor+eng', config=config)
                lines = result_text.split('\n')
                
                for line in lines:
                    ingredients = _processor.extract_ingredients_from_line(line)
                    all_ingredients.extend(ingredients)
                    
            except Exception as e:
                print(f"Tesseract {config_name} 처리 중 오류: {e}")
    
    if progress_callback:
        progress_callback(0.9, "결과 정제 중...")
    
    final_ingredients = _processor.post_process_ingredients(all_ingredients)
    
    if progress_callback:
        progress_callback(1.0, "완료!")
    
    return final_ingredients

def extract_ingredients_combined_with_progress(image_array: np.ndarray, progress_callback=None) -> dict:
    """진행률 콜백이 있는 결합 모드"""
    if progress_callback:
        progress_callback(0.1, "결합 모드 시작...")
    
    # EasyOCR 결과
    easyocr_ingredients = extract_ingredients_easyocr_with_progress(
        image_array, 
        lambda p, m: progress_callback(0.1 + p * 0.4, m) if progress_callback else None
    )
    
    if progress_callback:
        progress_callback(0.5, "Tesseract 처리 시작...")
    
    # Tesseract 결과  
    tesseract_ingredients = extract_ingredients_tesseract_with_progress(
        image_array,
        lambda p, m: progress_callback(0.5 + p * 0.4, m) if progress_callback else None  
    )
    
    if progress_callback:
        progress_callback(0.9, "결과 병합 중...")
    
    # 결과 병합
    combined_ingredients = _processor.post_process_ingredients(
        easyocr_ingredients + tesseract_ingredients
    )
    
    if progress_callback:
        progress_callback(1.0, "완료!")
    
    return {
        'combined': combined_ingredients,
        'easyocr_only': easyocr_ingredients,
        'tesseract_only': tesseract_ingredients,
        'easyocr_count': len(easyocr_ingredients),
        'tesseract_count': len(tesseract_ingredients),
        'combined_count': len(combined_ingredients)
    }