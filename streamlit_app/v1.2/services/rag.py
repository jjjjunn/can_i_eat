import os
from typing import Optional, List
from dotenv import load_dotenv
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain.chains import RetrievalQA
import logging
from services.memory_optimizer import MemoryOptimizer, ChunkedDocumentProcessor
import asyncio
from pathlib import Path
import nest_asyncio

nest_asyncio.apply()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 환경 변수
load_dotenv()

class RAGSystem:
    """기본 RAG 시스템"""
    
    def __init__(self, pdf_dir: str = "thesis"):
        """인스턴스 변수만 초기화"""
        self.pdf_dir = Path(pdf_dir)
        self.vectorstore = None
        self.qa_chain = None
        self.embeddings = None
        self._initialized = False
        
    def _initialize_sync(self):
        """비동기적으로 RAG 시스템을 초기화(내부용)"""
        if self._initialized:
            logger.info("RAG 시스템이 이미 초기화되어 있습니다.")
            return
        
        try:
            self._load_documents()
            self._create_vectorstore()
            self._setup_qa_chain()
            self._initialized = True
            logger.info("RAG 시스템 초기화 완료")
        except Exception as e:
            logger.error(f"RAG 시스템 초기화 실패: {e}")
            raise
    
    def initialize(self):
        """RAG 시스템을 초기화하는 공개 메서드"""
        self._initialize_sync()
       
    def _load_documents(self):
        """PDF 문서 로드"""
        pdf_files = ["Allergie.pdf", "Guideline.pdf"]
        all_documents = []
        
        if not self.pdf_dir.exists():
            raise FileNotFoundError(f"PDF 디렉토리가 존재하지 않습니다. {self.pdf_dir}")
        
        for filename in pdf_files:
            filepath = self.pdf_dir / filename
            if filepath.exists():
                try:
                    loader = PyMuPDFLoader(str(filepath))
                    documents = loader.load()
                    all_documents.extend(documents)
                    logger.info(f"{filename} 로드 완료 - {len(documents)}개 페이지")
                except Exception as e:
                    logger.warning(f"{filename} 로드 실패: {e}")

            else:
                logger.warning(f"파일을 찾을 수 없습니다: {filepath}")

        if not all_documents:
            raise ValueError("로드된 문서가 없습니다. PDF 파일 경로를 확인해 주세요")
        
        self.documents = all_documents
        logger.info(f"총 {len(all_documents)}개 문서 로드 완료")
    
    # async def _create_embeddings_async(self):
    #     """비동기 작업으로 감싸기"""
    #     return GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    
    def _create_vectorstore(self):
        """벡터 저장소 생성 또는 로드"""
        try:
            # 비동기 함수를 동기 함수에서 호출하기
            # self.embeddings =  asyncio.run(self._create_embeddings_async())
            
            index_path = "faiss_index_thesis"
            self.embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
            if os.path.exists(index_path):
                self.vectorstore = FAISS.load_local(
                    index_path,
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
                logger.info("기존 벡터 저장소 로드 완료")
                
            else:
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1000,
                    chunk_overlap=200,
                    length_function=len,
                    separators=["\n\n", "\n", " ", ""]
                )
                
                chunks = text_splitter.split_documents(self.documents)
                logger.info(f"문서를 {len(chunks)}개 청크로 분할 완료")
                
                self.vectorstore = FAISS.from_documents(chunks, self.embeddings)
                self.vectorstore.save_local(index_path)
                logger.info("새 벡터 저장소 생성 완료")
                
        except Exception as e:
            logger.error(f"벡터 저장소 생성/로드 실패: {e}")
            raise
    
    # async def _create_qa_chain_async():
    #     """비동기 작업으로 감싸기"""
    #     return ChatGoogleGenerativeAI(
    #         model='gemini-2.5-flash',
    #         temperature=0.1, # 약간의 창의성 허용
    #         )
    
    # QA 체인 설정
    def _setup_qa_chain(self):
        """QA 체인 설정"""
        if not self.vectorstore:
            raise ValueError("벡터 저장소가 초기화되지 않았습니다.")
        
        # 검색 파라미터
        # 검색기 (retriever) 설정
        retriever = self.vectorstore.as_retriever(
            search_type = "similarity",
            search_kwargs={"k": 5} # 상위 5개 문서 검색
        ) 
        
        # LLM 설정
        # llm = asyncio.run(self._create_qa_chain_async())
        llm = ChatGoogleGenerativeAI(
            model='gemini-2.5-flash',
            temperature=0.1,  # 약간의 창의성 허용
        )
        
        # RetrievalQA 체인 설정
        self.qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=retriever,
            return_source_documents=True, # 소스 문서도 반환
            verbose=False
        )
        logger.info("RAG QA 체인이 성공적으로 초기화되었습니다.")

    def query(self, question: str) -> dict: 
        """질의 처리"""
        if not self.qa_chain:
            raise ValueError("QA 체인이 초기화되지 않았습니다.")
        
        if not question.strip():
            raise ValueError("질문이 비어있습니다.")
        
        try:
            result = self.qa_chain.invoke({"query": question})
            return {
                "answer": result.get('result', ''),
                "sources": result.get('source_documents', [])
            }
        except Exception as e:
            logger.error(f"질의 처리 중 오류: {e}")
            raise
        
    def is_initialized(self) -> bool:
        """초기화 상태 확인"""
        return self._initialized

# 메모리 최적화 적용된 RAG 시스템 (기존 RAG 시스템을 상속받음)
class OptimizedRAGSystem(RAGSystem):
    """메모리 최적화가 적용된 RAG 시스템"""
    
    def __init__(self, pdf_dir: str = "thesis", use_memory_optimization: bool = True):
        # 부모 클래스의 __init__ 호출
        super().__init__(pdf_dir)
        self.use_memory_optimization = use_memory_optimization
        self.memory_optimizer = MemoryOptimizer() if use_memory_optimization else None
        self.chunk_processor = ChunkedDocumentProcessor() if use_memory_optimization else None
    
    def _create_vectorstore(self):
        """메모리 최적화가 적용된 벡터 저장소 생성"""
        if self.memory_optimizer:
            self.memory_optimizer.log_memory_usage("벡터 저장소 생성 전")
        
        try:
            self.embeddings = GoogleGenerativeAIEmbeddings(
                model="models/embedding-001"
            )
            index_path = "faiss_index_thesis"
            
            if os.path.exists(index_path):
                self.vectorstore = FAISS.load_local(
                    index_path, 
                    self.embeddings, 
                    allow_dangerous_deserialization=True
                )
                logger.info("기존 벡터 저장소 로드 완료")
            else:
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1000, 
                    chunk_overlap=200,
                    length_function=len,
                    separators=["\n\n", "\n", " ", ""]
                )
                chunks = text_splitter.split_documents(self.documents)
                logger.info(f"문서를 {len(chunks)}개 청크로 분할")
                
                if self.use_memory_optimization and len(chunks) > 1000:
                    logger.info("대용량 문서 감지 - 점진적 처리 모드")
                    # 대용량 문서의 경우 점진적 처리
                    self.vectorstore = self.chunk_processor.create_vectorstore_incrementally(
                        chunks, self.embeddings, index_path
                    )
                else:
                    # 일반적인 처리
                    self.vectorstore = FAISS.from_documents(chunks, self.embeddings)
                    self.vectorstore.save_local(index_path)
                
                logger.info("새 벡터 저장소 생성 완료")
        
        except Exception as e:
            logger.error(f"최적화된 벡터 저장소 생성 실패: {e}")
            raise
        
        finally:
            if self.memory_optimizer:
                self.memory_optimizer.log_memory_usage("벡터 저장소 생성 후")
                self.memory_optimizer.force_garbage_collection()

    def get_memory_stats(self) -> dict:
        """메모리 사용량 통계 반환"""
        if self.memory_optimizer:
            return self.memory_optimizer.get_memory_stats()
        return {"message": "메모리 최적화가 비활성화됨"}
    
# 팩토리 패턴으로 RAG 시스템 생성
class RAGSystemFactory:
    """RAG 시스템 팩토리"""
    
    @staticmethod
    def create_rag_system(optimized: bool = True, **kwargs) -> RAGSystem:
        """RAG 시스템 인스턴스 생성"""
        if optimized:
            return OptimizedRAGSystem(**kwargs)
        else:
            return RAGSystem(**kwargs)