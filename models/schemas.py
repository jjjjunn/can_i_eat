from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

class BaseResponse(BaseModel):
    """기본 응답 모델"""
    success: bool = True
    message: str = "요청이 성공적으로 처리되었습니다"

class OcrResponse(BaseResponse):
    """OCR 분석 응답 모델"""
    extracted_ingredients: List[str]
    processing_time: float
    ingredients_count: int
    image_path: Optional[str] = None  # 저장된 이미지 경로
    
    def __init__(self, **data):
        if 'extracted_ingredients' in data:
            data['ingredients_count'] = len(data['extracted_ingredients'])
        super().__init__(**data)

class AnalysisRequest(BaseModel):
    """챗봇 분석 요청 모델"""
    ingredients: List[str] = Field(..., min_items=1, description="분석할 성분 목록")
    user_id: str = Field(..., description="사용자 ID")  # UUID에서 str로 변경
    image_url: Optional[str] = Field(None, description="이미지 URL")
    ocr_result: Optional[Dict[str, Any]] = Field(None, description="OCR 결과 데이터")

class AnalysisResponse(BaseResponse):
    """챗봇 분석 응답 모델"""
    chatbot_result: str = Field(..., description="AI 분석 결과")
    user_food_log_id: UUID = Field(..., description="저장된 기록의 ID")
    analysis_summary: Optional[Dict[str, Any]] = None

class FoodLogResponse(BaseModel):
    """사용자 음식 기록 조회 응답 모델"""
    id: UUID
    image_url: str
    ocr_result: Dict[str, Any]
    gemini_response: Dict[str, Any]
    created_at: datetime
    ingredients_count: int = 0
    
    def __init__(self, **data):
        # OCR 결과에서 성분 개수 계산
        if 'ocr_result' in data and 'extracted_ingredients' in data['ocr_result']:
            data['ingredients_count'] = len(data['ocr_result']['extracted_ingredients'])
        super().__init__(**data)

class UserFoodLogsResponse(BaseResponse):
    """사용자 전체 기록 조회 응답 모델"""
    logs: List[FoodLogResponse]
    total_count: int
    
    def __init__(self, **data):
        if 'logs' in data:
            data['total_count'] = len(data['logs'])
        super().__init__(**data)