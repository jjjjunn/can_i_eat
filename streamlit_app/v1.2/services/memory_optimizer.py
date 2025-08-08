import gc
import psutil # 컴퓨터의 성능이나 정보 확인
import logging
from typing import Iterator, List
from langchain.schema import Document

logger = logging.getLogger(__name__)

class MemoryOptimizer:
    """메모리 사용량 최적화를 위한 유틸리티 클래스"""
    
    @staticmethod
    def get_memory_usage() -> dict:
        """현재 메모리 사용량 반환"""
        process = psutil.Process()
        memory_info = process.memory_info()
        return {
            'rss': memory_info.rss / 1024 / 1024,  # MB
            'vms': memory_info.vms / 1024 / 1024,  # MB
            'percent': process.memory_percent()
        }
    
    @staticmethod
    def log_memory_usage(stage: str):
        """메모리 사용량 로깅"""
        memory = MemoryOptimizer.get_memory_usage()
        logger.info(f"[{stage}] Memory: RSS={memory['rss']:.1f}MB, "
                   f"VMS={memory['vms']:.1f}MB, Percent={memory['percent']:.1f}%")
    
    @staticmethod
    def force_garbage_collection():
        """강제 가비지 컬렉션"""
        before = MemoryOptimizer.get_memory_usage()
        gc.collect()
        after = MemoryOptimizer.get_memory_usage()
        freed = before['rss'] - after['rss']
        logger.info(f"Garbage collection freed {freed:.1f}MB")

class ChunkedDocumentProcessor:
    """대용량 문서를 청크 단위로 처리하는 클래스"""
    
    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size
        self.memory_optimizer = MemoryOptimizer()
    
    def process_documents_in_batches(self, documents: List[Document]) -> Iterator[List[Document]]:
        """문서를 배치 단위로 처리"""
        total_docs = len(documents)
        logger.info(f"Processing {total_docs} documents in batches of {self.batch_size}")
        
        for i in range(0, total_docs, self.batch_size):
            batch = documents[i:i + self.batch_size]
            
            self.memory_optimizer.log_memory_usage(f"Batch {i//self.batch_size + 1}")
            
            yield batch
            
            # 배치 처리 후 메모리 정리
            if i > 0 and i % (self.batch_size * 5) == 0:
                self.memory_optimizer.force_garbage_collection()
    
    def create_vectorstore_incrementally(self, documents: List[Document], embeddings, 
                                       vectorstore_path: str):
        """점진적으로 벡터 저장소 생성"""
        from langchain_community.vectorstores import FAISS
        
        vectorstore = None
        
        for batch_num, batch in enumerate(self.process_documents_in_batches(documents)):
            logger.info(f"Processing batch {batch_num + 1}")
            
            if vectorstore is None:
                # 첫 번째 배치로 벡터 저장소 초기화
                vectorstore = FAISS.from_documents(batch, embeddings)
            else:
                # 기존 벡터 저장소에 추가
                temp_vectorstore = FAISS.from_documents(batch, embeddings)
                vectorstore.merge_from(temp_vectorstore)
                del temp_vectorstore
            
            # 주기적으로 저장
            if batch_num % 10 == 0:
                vectorstore.save_local(f"{vectorstore_path}_temp_{batch_num}")
                logger.info(f"Intermediate save completed for batch {batch_num}")
        
        # 최종 저장
        if vectorstore:
            vectorstore.save_local(vectorstore_path)
            logger.info("Final vectorstore saved")
        
        return vectorstore