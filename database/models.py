from datetime import datetime
from typing import Optional, List
from uuid import UUID, uuid4

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field, Relationship

class Role(SQLModel, table=True):
    """사용자 역할 테이블"""
    __tablename__ = 'roles'
    __table_args__ = {"extend_existing": True}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True, max_length=50)
    description: Optional[str] = Field(default=None, max_length=255)
    
    # 관계 설정
    users: List["User"] = Relationship(back_populates="role")

class User(SQLModel, table=True):
    """사용자 정보 테이블"""
    __tablename__ = 'users'
    __table_args__ = {"extend_existing": True}
    
    id: Optional[str] = Field(default=None, primary_key=True)  # 소셜 로그인 ID 지원
    email: str = Field(unique=True, index=True, max_length=255)
    name: str = Field(max_length=100)
    provider: str = Field(max_length=50)  # google, kakao 등
    provider_id: str = Field(max_length=255)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = None
    
    # 외래키
    role_id: int = Field(foreign_key="roles.id")
    
    # 관계 설정
    role: Role = Relationship(back_populates="users")
    food_logs: List["UserFoodLog"] = Relationship(back_populates="user")
    activities: List["UserActivity"] = Relationship(back_populates="user")

class UserFoodLog(SQLModel, table=True):
    """음식 성분 분석 기록 테이블"""
    __tablename__ = 'user_food_logs'
    __table_args__ = {"extend_existing": True}
    
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    image_url: str = Field(max_length=500)
    ocr_result: dict = Field(sa_column=Column(JSONB))  # OCR 추출 결과
    gemini_prompt: str = Field(max_length=2000)  # AI에게 보낸 프롬프트
    gemini_response: dict = Field(sa_column=Column(JSONB))  # AI 응답 결과
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # 외래키 - 문자열로 변경
    user_id: str = Field(foreign_key="users.id")
    
    # 관계 설정
    user: User = Relationship(back_populates="food_logs")

class UserActivity(SQLModel, table=True):
    """사용자 활동 로그 테이블"""
    __tablename__ = 'user_activities'
    __table_args__ = {"extend_existing": True}
    
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    action_type: str = Field(max_length=100)  # ocr_analysis, chatbot_analysis 등
    details: dict = Field(sa_column=Column(JSONB))  # 활동 상세 정보
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # 외래키 - 문자열로 변경
    user_id: str = Field(foreign_key="users.id")
    
    # 관계 설정
    user: User = Relationship(back_populates="activities")