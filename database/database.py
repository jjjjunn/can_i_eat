import os
from fastapi import Request
from contextlib import contextmanager
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import User
from sqlalchemy.orm import Session
from sqlmodel import SQLModel

# .env 파일에서 환경변수 로드
load_dotenv()

# 데이터베이스 URL 검증 및 설정
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    print("⚠️ DATABASE_URL이 설정되지 않았습니다! .env 파일을 확인해 주세요.")
    # 개발 환경에서는 기본값 사용
    DATABASE_URL = "sqlite:///./test.db"
    print(f"⚠️ 개발용 SQLite 데이터베이스를 사용합니다: {DATABASE_URL}")

print(f"📦 DATABASE_URL 설정됨: {DATABASE_URL[:20]}...")

# 엔진 및 세션 생성
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_db_and_tables():
    """데이터베이스 테이블 생성"""
    try:
        print("📦 데이터베이스 모델 import 중...")
        import database.models  # models.py에서 모든 테이블 정의를 import
        
        print("🔨 테이블 생성 중...")
        # Base.metadata.create_all(bind=engine)
        SQLModel.metadata.create_all(engine)
        
        # 생성된 테이블 목록 확인
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"✅ 테이블 생성 완료: {tables}")
        
    except Exception as e:
        print(f"❌ 테이블 생성 실패: {e}")
        raise

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 데이터베이스 연결 테스트
def test_connection():
    """데이터베이스 연결 테스트"""
    try:
        with engine.connect():
            print("✅ 데이터베이스 연결 성공!")
            return True
    except Exception as e:
        print(f"❌ 데이터베이스 연결 실패: {e}")
        return False
