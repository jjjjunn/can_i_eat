import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session

from services.ocr_service import VisionTextExtractor
from services.chatbot import IngredientsAnalyzer
from services.rag import OptimizedRAGSystem
from database.models import UserFoodLog
from models.schemas import OcrResponse, AnalysisResponse

# 로깅 설정
logger = logging.getLogger(__name__)

class ServiceManager:
    """서비스들을 관리하는 싱글톤 클래스"""
    
    _instance = None
    _rag_system = None
    _analyzer = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @property
    def rag_system(self) -> OptimizedRAGSystem:
        """RAG 시스템 인스턴스 반환"""
        if self._rag_system is None:
            logger.info("RAG 시스템 초기화 중...")
            self._rag_system = OptimizedRAGSystem()
            self._rag_system.initialize()
            logger.info("RAG 시스템 초기화 완료")
        return self._rag_system
    
    @property
    def analyzer(self) -> IngredientsAnalyzer:
        """분석기 인스턴스 반환"""
        if self._analyzer is None:
            logger.info("성분 분석기 초기화 중...")
            self._analyzer = IngredientsAnalyzer()
            logger.info("성분 분석기 초기화 완료")
        return self._analyzer

# 전역 서비스 매니저 인스턴스
service_manager = ServiceManager()

async def perform_ocr_analysis(
    file_bytes: bytes, 
    file_name: str,
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> OcrResponse:
    """
    이미지 파일의 OCR 분석 수행
    
    Args:
        file_bytes: 이미지 파일 바이트 데이터
        file_name: 파일 이름
        progress_callback: 진행률 콜백 함수
        
    Returns:
        OcrResponse: OCR 분석 결과
    """
    start_time = time.time()
    tmp_file_path = ""
    
    try:
        # 임시 파일 생성
        with tempfile.NamedTemporaryFile(
            delete=False, 
            suffix=Path(file_name).suffix
        ) as tmp_file:
            tmp_file.write(file_bytes)
            tmp_file_path = tmp_file.name

        # OCR 추출 수행
        extractor = VisionTextExtractor(api_endpoint='eu-vision.googleapis.com')
        
        if progress_callback:
            extracted_list = extractor.extract_ingredients_with_progress(
                tmp_file_path, progress_callback
            )
        else:
            extracted_list = extractor.extract_ingredients(tmp_file_path)
        
        if not extracted_list:
            raise ValueError("성분을 추출하지 못했습니다.")
            
        processing_time = time.time() - start_time
        
        return OcrResponse(
            extracted_ingredients=extracted_list,
            processing_time=processing_time,
            message=f"{len(extracted_list)}개 성분이 성공적으로 추출되었습니다."
        )
        
    except Exception as e:
        logger.error(f"OCR 분석 오류: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"이미지 분석 중 오류가 발생했습니다: {e}"
        )
    finally:
        # 임시 파일 정리
        if tmp_file_path and os.path.exists(tmp_file_path):
            try:
                os.remove(tmp_file_path)
            except Exception as e:
                logger.warning(f"임시 파일 삭제 실패: {e}")

def perform_chatbot_analysis_and_save(
    ingredients: List[str],
    user_id: UUID,
    session: Session,
    image_url: Optional[str] = None,
    ocr_result: Optional[Dict[str, Any]] = None
) -> AnalysisResponse:
    """
    성분 목록 기반 챗봇 분석 수행 및 DB 저장
    
    Args:
        ingredients: 성분 목록
        user_id: 사용자 ID
        session: 데이터베이스 세션
        image_url: 이미지 URL
        ocr_result: OCR 결과
        
    Returns:
        AnalysisResponse: 분석 결과
    """
    try:
        # 챗봇 분석 수행
        analyzer = service_manager.analyzer
        rag_system = service_manager.rag_system
        
        chatbot_result_text = analyzer.analyze_ingredients(
            ingredients_list=ingredients,
            use_rag=True,
            rag_system=rag_system
        )
        
        # 응답 데이터 구조화
        gemini_response_dict = {
            "text_response": chatbot_result_text,
            "analysis_timestamp": time.time(),
            "ingredients_analyzed": len(ingredients)
        }
        
        # OCR 결과가 없으면 성분 목록을 기반으로 생성
        if ocr_result is None:
            ocr_result = {
                "extracted_ingredients": ingredients,
                "processing_time": 0.0,
                "source": "manual_input"
            }
        
        # 데이터베이스에 저장
        new_log = UserFoodLog(
            user_id=user_id,
            image_url=image_url or "",
            ocr_result=ocr_result,
            gemini_prompt=" | ".join(ingredients),  # 구분자로 성분 결합
            gemini_response=gemini_response_dict
        )
        
        session.add(new_log)
        session.commit()
        session.refresh(new_log)
        
        # 분석 요약 생성
        analysis_summary = {
            "total_ingredients": len(ingredients),
            "analysis_type": "rag_enabled",
            "processing_time": time.time() - (gemini_response_dict.get("analysis_timestamp", time.time()))
        }
        
        return AnalysisResponse(
            chatbot_result=chatbot_result_text,
            user_food_log_id=new_log.id,
            analysis_summary=analysis_summary,
            message="성분 분석이 완료되고 기록에 저장되었습니다."
        )
        
    except Exception as e:
        logger.error(f"챗봇 분석 및 저장 오류: {e}")
        session.rollback()
        raise HTTPException(
            status_code=500, 
            detail=f"챗봇 분석 중 오류가 발생했습니다: {e}"
        )

def initialize_services():
    """서비스들을 초기화합니다."""
    try:
        # 서비스 매니저를 통해 모든 서비스 초기화
        _ = service_manager.rag_system
        _ = service_manager.analyzer
        logger.info("모든 서비스 초기화 완료")
        return True
    except Exception as e:
        logger.error(f"서비스 초기화 실패: {e}")
        return False