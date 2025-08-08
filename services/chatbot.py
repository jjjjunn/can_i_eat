import google.generativeai as genai
import os
import logging
from typing import List, Optional
from services.rag import RAGSystem

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# 클래스 기반 구조
class IngredientsAnalyzer:
    def __init__(self):
        self.gemini_model = None # 챗봇 모델 초기화
        self.rag_system = None # RAG 시스템 초기화
        self._initialize_models()
        
    def _initialize_models(self):
        """모델 초기화"""
        # genai_key = os.getenv("GOOGLE_API_KEY") # 제미나이 API 불러오기
        genai_key = st.secrets['GOOGLE_API_KEY']['GOOGLE_API_KEY']
        if not genai_key:
            raise ValueError("GOOGLE_API_KEY 환경 변수가 설정되지 않았습니다.")

        genai.configure(api_key = genai_key)
        
        try:
            self.gemini_model = genai.GenerativeModel('gemini-2.5-flash')
            self.rag_system = RAGSystem()
            logger.info("모델 초기화 완료")
        except Exception as e:
            logger.error(f"모델 초기화 실패: {e}")
            raise

    # 성분 분석 수행
    def analyze_ingredients(self, ingredients_list: List[str], use_rag: bool = False, rag_system=None) -> str:
        """성분 분석 수행"""
        if not ingredients_list:
            return "분석할 성분 목록이 제공되지 않았습니다."
        
        try:
            if use_rag and rag_system:
                return self._analyze_with_rag(ingredients_list, rag_system)
            else:
                if use_rag and not rag_system:
                    logger.warning("RAG 사용이 활성화되었으나, RAG 시스템이 준비되지 않았습니다.")
                    
                return self._analyze_with_gemini(ingredients_list)
        except Exception as e:
            logger.error(f"분석 중 오류 발생: {e}")
            return "분석 중 오류가 발생했습니다 잠시 후 다시 시도해 주세요."
        
        
    # 제미나이 모델을 사용한 성분 분석
    def _analyze_with_gemini(self, ingredients_list: List[str]) -> str:
        """Gemini 모델을 사용한 성분 분석"""
        if not self.gemini_model:
            raise ValueError("Gemini 모델이 초기화되지 않았습니다.")
        
        # 프롬프트 구성
        # join 함수로 리스트를 문자열로 변환하여 프롬프트에 삽입
        ingredients_str = ', '.join(ingredients_list)
        prompt = f"""
        당신은 임신부를 위한 식품 성분 분석 전문가 챗봇입니다.
        사용자는 임신부가 특정 식품을 섭취해도 되는지 궁금해합니다.
        아래는 식품 성분표에서 추출된 성분 목록입니다.
        
        추출된 성분 목록:
        {ingredients_str}
        
        이 정보를 바탕으로, 다음 지침에 따라 임신부가 이 식품을 섭취해도 되는지 여부를 판단하여 간결하고 명확하게 설명해 주세요.

        1.  **최종 판단:** 반드시 '섭취 가능', '섭취 주의', '섭취 불가' 중 하나로 명시해야 합니다.
        2.  **주의 성분 명시:** 만약 섭취에 주의가 필요하거나 피해야 하는 성분이 있다면, 그 성분명과 함께 왜 주의해야 하는지(예: 알레르기 유발, 태아에 해로울 수 있는 성분, 과다 섭취 시 문제 등) 구체적으로 설명해 주세요.
        3.  **섭취 시 유의 사항:** 섭취 시 어떤 점을 유의해야 하는지 친절하게 알려주세요.
        4.  **면책 조항:** 모든 정보는 일반적인 정보이며, 의학적 조언을 대체할 수 없다는 면책 조항을 반드시 포함해 주세요.

        예시 응답 형식:
        [최종 판단]
        [주의 성분 및 설명]
        [섭취 시 유의 사항]
        [면책 조항]
        """
        logger.info(f"Gemini API 호출 - 성분 개수: {len(ingredients_list)}")
        
        try:
            # 모델에 프롬프트 전달 및 응답 생성
            response = self.gemini_model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini API 호출 실패: {e}")
            raise
        
    # RAG를 활용, 논문에서 데이터를 검색하여 보다 정확한 정보 제공
    def _analyze_with_rag(self, ingredients_list: List[str], rag_system) -> str:
        """
        RAG 시스템을 활용하여 식품 성분 분석 결과에 대한 섭취 가능 여부를 안내합니다.
        논문에서 검색된 정보를 바탕으로 Gemini 모델이 답변을 생성합니다.

        Args:
            ingredients_list (list): 식품 성분 목록
            rag_systen: RAG 시스템 객체 (query 메서드를 가지고 있어야 함)

        Returns:
            str: Gemini 모델의 분석 결과 텍스트. 오류 발생 시 오류 메시지.
        """
        if not rag_system or not hasattr(rag_system, 'query'):
            raise ValueError("유효한 RAG 시스템이 객체가 제공되지 않았습니다.")
        
        ingredients_str = ', '.join(ingredients_list)
        prompt = f"""
        당신은 임신부를 위한 식품 성분 분석 전문가이자 친절한 상담사입니다.
        사용자는 임신부가 특정 식품을 섭취해도 되는지 궁금해합니다.
        아래는 식품 성분표에서 추출된 성분 목록입니다.
        
        추출된 성분 목록:
        {ingredients_str}
        
        이 정보를 바탕으로, 다음 지침에 따라 임신부가 이 식품을 섭취해도 되는지 여부를 판단하여, 친절하고 부드럽게 설명해 주세요.
        답변을 생성할 때, 제공된 논문 자료에서 관련 정보를 적극적으로 검색하고 활용하세요.

        이 정보를 바탕으로, 다음 지침에 따라 임신부가 이 식품을 섭취해도 되는지 여부를 판단하여, 친절하고 부드러운 문체로 답변해 주세요.

        1.  **결론부터 명확하게 제시:** 가장 먼저 이 식품이 '섭취 가능', '섭취 주의', '섭취 불가' 중 어디에 해당하는지 부드러운 문장으로 알려주세요.
        2.  **주의 성분은 친절하게 설명:** 만약 주의가 필요한 성분이 있다면, 그 성분이 무엇이고 왜 주의해야 하는지 검색된 정보를 참고하여 구체적으로 설명해 주세요. 이때 논문 내용을 딱딱하게 인용하기보다, 이해하기 쉬운 말로 풀어서 설명해 주세요.
        3.  **섭취 시 유의사항 안내:** 섭취 시 어떤 점을 고려해야 하는지 부드러운 말투로 조언해 주세요. 예시로 제공된 내용처럼 균형 잡힌 식사의 중요성이나, 다른 보충제와의 중복 섭취를 피하라는 등의 내용을 포함할 수 있습니다.
        4.  **면책 조항 포함:** 답변 마지막에 "이 정보는 일반적인 참고용이며, 개인의 건강 상태에 대해서는 반드시 의사 또는 약사와 상담이 필요합니다."와 같은 면책 조항을 자연스럽게 덧붙여 주세요.

        예시 응답 형식:
        [최종 판단]
        [주의 성분 및 설명]
        [섭취 시 유의 사항]
        [면책 조항]
        """
        
        logger.info(f"RAG 시스템 호출 - 성분 개수: {len(ingredients_list)}")

        try:
            rag_result = rag_system.query(prompt)
            
            # 사용자에게는 답변만 보이도록 설정
            return rag_result.get('answer', '답변을 생성할 수 없습니다.')
        except Exception as e:
            logger.error(f"RAG 시스템 호출 실패: {e}")

            raise
