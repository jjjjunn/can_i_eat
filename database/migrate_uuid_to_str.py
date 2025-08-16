"""
데이터베이스 마이그레이션 스크립트
UUID 기반 사용자 ID를 문자열 기반으로 변경
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

def migrate_uuid_to_str():
    """UUID 기반 사용자 ID를 문자열로 마이그레이션"""
    
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
                logger.info("마이그레이션 시작...")
                
                # 1. 기존 테이블 백업 (선택사항)
                logger.info("기존 테이블 백업 중...")
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS users_backup AS 
                    SELECT * FROM users
                """))
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS user_food_logs_backup AS 
                    SELECT * FROM user_food_logs
                """))
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS user_activities_backup AS 
                    SELECT * FROM user_activities
                """))
                
                # 2. 외래키 제약 조건 제거
                logger.info("외래키 제약 조건 제거 중...")
                conn.execute(text("""
                    ALTER TABLE user_food_logs 
                    DROP CONSTRAINT IF EXISTS user_food_logs_user_id_fkey
                """))
                conn.execute(text("""
                    ALTER TABLE user_activities 
                    DROP CONSTRAINT IF EXISTS user_activities_user_id_fkey
                """))
                
                # 3. user_id 컬럼 타입 변경
                logger.info("user_id 컬럼 타입 변경 중...")
                conn.execute(text("""
                    ALTER TABLE user_food_logs 
                    ALTER COLUMN user_id TYPE VARCHAR(255)
                """))
                conn.execute(text("""
                    ALTER TABLE user_activities 
                    ALTER COLUMN user_id TYPE VARCHAR(255)
                """))
                
                # 4. users 테이블의 id 컬럼 타입 변경
                logger.info("users 테이블 id 컬럼 타입 변경 중...")
                conn.execute(text("""
                    ALTER TABLE users 
                    ALTER COLUMN id TYPE VARCHAR(255)
                """))
                
                # 5. 외래키 제약 조건 재생성
                logger.info("외래키 제약 조건 재생성 중...")
                conn.execute(text("""
                    ALTER TABLE user_food_logs 
                    ADD CONSTRAINT user_food_logs_user_id_fkey 
                    FOREIGN KEY (user_id) REFERENCES users(id)
                """))
                conn.execute(text("""
                    ALTER TABLE user_activities 
                    ADD CONSTRAINT user_activities_user_id_fkey 
                    FOREIGN KEY (user_id) REFERENCES users(id)
                """))
                
                # 트랜잭션 커밋
                trans.commit()
                logger.info("마이그레이션 완료!")
                return True
                
            except Exception as e:
                # 오류 발생 시 롤백
                trans.rollback()
                logger.error(f"마이그레이션 실패: {e}")
                return False
                
    except Exception as e:
        logger.error(f"데이터베이스 연결 실패: {e}")
        return False

def check_migration_status():
    """마이그레이션 상태 확인"""
    
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        logger.error("DATABASE_URL이 설정되지 않았습니다!")
        return False
    
    engine = create_engine(DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            # users 테이블의 id 컬럼 타입 확인
            result = conn.execute(text("""
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'id'
            """)).fetchone()
            
            if result:
                logger.info(f"users.id 컬럼 타입: {result[0]}")
                return result[0] == 'character varying'
            else:
                logger.warning("users 테이블을 찾을 수 없습니다.")
                return False
                
    except Exception as e:
        logger.error(f"상태 확인 실패: {e}")
        return False

if __name__ == "__main__":
    logger.info("데이터베이스 마이그레이션 도구")
    
    # 현재 상태 확인
    if check_migration_status():
        logger.info("이미 마이그레이션이 완료되었습니다.")
    else:
        logger.info("마이그레이션이 필요합니다.")
        
        # 사용자 확인
        response = input("마이그레이션을 진행하시겠습니까? (y/N): ")
        if response.lower() == 'y':
            if migrate_uuid_to_str():
                logger.info("마이그레이션이 성공적으로 완료되었습니다!")
            else:
                logger.error("마이그레이션에 실패했습니다.")
        else:
            logger.info("마이그레이션이 취소되었습니다.")
