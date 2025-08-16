"""
데이터베이스 초기화 스크립트
기존 테이블을 삭제하고 새로운 스키마로 재생성
"""
import os
import logging
from sqlalchemy import text, create_engine
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reset_database():
    """데이터베이스 초기화"""
    
    # 데이터베이스 연결
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        logger.error("DATABASE_URL이 설정되지 않았습니다!")
        return False
    
    engine = create_engine(DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            # 트랜잭션 시작
            trans = conn.begin()
            
            try:
                logger.info("데이터베이스 초기화 시작...")
                
                # 1. 기존 테이블 삭제 (순서 중요: 외래키 참조 순서 고려)
                logger.info("기존 테이블 삭제 중...")
                conn.execute(text("DROP TABLE IF EXISTS user_activities CASCADE"))
                conn.execute(text("DROP TABLE IF EXISTS user_food_logs CASCADE"))
                conn.execute(text("DROP TABLE IF EXISTS users CASCADE"))
                conn.execute(text("DROP TABLE IF EXISTS roles CASCADE"))
                
                # 2. 새로운 테이블 생성
                logger.info("새로운 테이블 생성 중...")
                
                # roles 테이블
                conn.execute(text("""
                    CREATE TABLE roles (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(50) UNIQUE NOT NULL,
                        description VARCHAR(255)
                    )
                """))
                
                # users 테이블 (문자열 ID 사용)
                conn.execute(text("""
                    CREATE TABLE users (
                        id VARCHAR(255) PRIMARY KEY,
                        email VARCHAR(255) UNIQUE NOT NULL,
                        name VARCHAR(100) NOT NULL,
                        provider VARCHAR(50) NOT NULL,
                        provider_id VARCHAR(255) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_login_at TIMESTAMP,
                        role_id INTEGER REFERENCES roles(id)
                    )
                """))
                
                # user_food_logs 테이블
                conn.execute(text("""
                    CREATE TABLE user_food_logs (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        image_url VARCHAR(500),
                        ocr_result JSONB,
                        gemini_prompt VARCHAR(2000),
                        gemini_response JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        user_id VARCHAR(255) REFERENCES users(id)
                    )
                """))
                
                # user_activities 테이블
                conn.execute(text("""
                    CREATE TABLE user_activities (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        action_type VARCHAR(100),
                        details JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        user_id VARCHAR(255) REFERENCES users(id)
                    )
                """))
                
                # 3. 기본 역할 생성
                logger.info("기본 역할 생성 중...")
                conn.execute(text("""
                    INSERT INTO roles (name, description) 
                    VALUES ('user', '일반 사용자')
                    ON CONFLICT (name) DO NOTHING
                """))
                
                # 트랜잭션 커밋
                trans.commit()
                logger.info("데이터베이스 초기화 완료!")
                return True
                
            except Exception as e:
                # 오류 발생 시 롤백
                trans.rollback()
                logger.error(f"데이터베이스 초기화 실패: {e}")
                return False
                
    except Exception as e:
        logger.error(f"데이터베이스 연결 실패: {e}")
        return False

if __name__ == "__main__":
    logger.info("데이터베이스 초기화 도구")
    logger.warning("⚠️  이 작업은 모든 기존 데이터를 삭제합니다!")
    
    # 사용자 확인
    response = input("정말로 데이터베이스를 초기화하시겠습니까? (y/N): ")
    if response.lower() == 'y':
        if reset_database():
            logger.info("데이터베이스가 성공적으로 초기화되었습니다!")
        else:
            logger.error("데이터베이스 초기화에 실패했습니다.")
    else:
        logger.info("데이터베이스 초기화가 취소되었습니다.")
