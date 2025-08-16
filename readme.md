# 먹어도 돼? (임신부를 위한 성분 분석기)

AI 기반 음식 성분 분석 및 섭취 가이드 웹 서비스  
(GCP Cloud Run, FastAPI, Streamlit, Google Cloud Vision, Gemini, Cloud SQL, Cloud Storage 활용)

---

## 프로젝트 소개

- 임신부를 위한 음식 성분 분석 및 섭취 가능 여부 안내 서비스
- 이미지 업로드 → OCR 성분 추출 → AI 분석 → 기록 관리
- 소셜 로그인(Google, Kakao) 지원
- 분석 기록 DB 저장 및 조회/삭제 기능
- GCP Cloud Run, Cloud SQL(PostgreSQL), Cloud Storage 연동

---

## 데모 사이트

- **서비스 URL:** [ ](서비스 주소 입력)

---

## 주요 기능

- 이미지 기반 성분표 OCR 추출
- AI(Gemini) 기반 섭취 가능 여부 분석
- 분석 결과 다운로드(TXT/JSON)
- 사용자별 분석 기록 관리(조회/삭제)
- 소셜 로그인(Google, Kakao)
- 관리자 페이지(전체 기록 조회/삭제)

---

## 기술 스택

| 구분         | 사용 기술/서비스                |
| ------------ | ------------------------------ |
| 백엔드       | FastAPI, SQLModel, SQLAlchemy  |
| 프론트엔드   | Streamlit                      |
| AI           | Google Gemini, RAG             |
| OCR          | Google Cloud Vision API        |
| DB           | Cloud SQL (PostgreSQL)         |
| 이미지 저장  | Cloud Storage                  |
| 인증         | JWT, OAuth2 (Google/Kakao)     |
| 배포         | GCP Cloud Run, Docker, Nginx   |

---

## 폴더 구조

```
can_i_eat_st/
├── app.py                # Streamlit 메인 앱
├── main.py               # FastAPI 백엔드
├── database/             # DB 모델 및 연결
├── models/               # Pydantic 스키마
├── services/             # OCR/AI 서비스
├── oauth/                # 소셜 로그인/연동 해제
├── utils/                # 유틸리티 함수/클래스
├── pages/                # Streamlit 페이지
├── requirements.txt      # Python 패키지 목록
├── Dockerfile            # 컨테이너 빌드 파일
├── nginx.conf            # Nginx 리버스 프록시 설정
├── supervisord.conf      # 프로세스 관리 설정
├── .env / env.yaml       # 환경 변수 파일
└── README.md             # 프로젝트 설명
```

---

## 설치 및 실행 방법

### 1. 환경 변수 설정

- `.env` 또는 `env.yaml` 파일에 아래 항목을 채워주세요:

```
DATABASE_URL=
GCS_BUCKET_NAME=
GOOGLE_API_KEY=
OPENAI_API_KEY=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=
KAKAO_REST_API_KEY=
KAKAO_CLIENT_SECRET=
KAKAO_REDIRECT_URI=
JWT_SECRET_KEY=
API_URL=
STREAMLIT_APP_URL=
...
```

### 2. 로컬 실행

```bash
# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # (Windows: venv\Scripts\activate)

# 패키지 설치
pip install --upgrade pip
pip install -r requirements.txt

# DB 테이블 생성
python -c "from database.database import create_db_and_tables; create_db_and_tables()"

# FastAPI 실행
uvicorn main:app --host 0.0.0.0 --port 8000

# Streamlit 실행
streamlit run app.py
```

### 3. Docker & Cloud Run 배포

```bash
# Docker 이미지 빌드
docker build -t can-i-eat-st .

# 로컬 테스트
docker run -p 8080:8080 can-i-eat-st

# GCP Cloud Run 배포
gcloud run deploy can-i-eat-st --source . --region [리전명] --allow-unauthenticated
```

---

## GCP 연동 가이드

### 1. Cloud SQL(PostgreSQL) 연결

- Cloud SQL 인스턴스 생성
- DB/사용자/비밀번호 생성
- Cloud Run 환경변수에 `DATABASE_URL` 등록  
  예시:  
  ```
  postgresql://USER:PASSWORD@/cloudsql/INSTANCE_CONNECTION_NAME/DB_NAME
  ```

### 2. Cloud Storage 이미지 저장

- 버킷 생성 및 권한 부여
- 환경변수 `GCS_BUCKET_NAME` 등록
- 서비스 계정 키 파일(GOOGLE_APPLICATION_CREDENTIALS) 등록

### 3. Vision API & Gemini API 연동

- API 키 발급 및 환경변수 등록

---

## 사용법

1. 소셜 로그인(Google/Kakao)으로 접속
2. 이미지 업로드 → 성분 추출 → AI 분석
3. 분석 결과 다운로드/기록 관리
4. 관리자 페이지에서 전체 기록 조회/삭제

---

## 주요 파일 설명

| 파일/폴더         | 설명                           |
| ----------------- | ------------------------------ |
| app.py            | Streamlit 프론트엔드           |
| main.py           | FastAPI 백엔드                 |
| database/models.py| DB 테이블 모델                 |
| models/schemas.py | API 응답/요청 스키마           |
| services/         | OCR/AI 분석 서비스             |
| oauth/            | 소셜 로그인/연동 해제          |
| utils/            | 유틸리티 함수/클래스           |
| pages/            | Streamlit 페이지               |
| requirements.txt  | 패키지 목록                    |
| Dockerfile        | 컨테이너 빌드 파일             |
| nginx.conf        | Nginx 리버스 프록시 설정       |
| supervisord.conf  | 프로세스 관리 설정             |

---

## 참고 링크

- [공식 문서]( )
- [데모 영상]( )
- [관련 논문/자료]( )

---

## 개발자 정보

- 이름:
- 이메일:
- 기타 연락처:

---

## TODO

- [ ] GCP 배포 자동화 스크립트 추가
- [ ] 관리자 기능 고도화
- [ ] 성분 DB/AI 모델 개선
- [ ] 테스트 코드 작성
- [ ] 기타

---

## 라이선스

(라이선스 정보 입력)

---

## 변경 이력

| 날짜       | 변경 내용         |
| ---------- | ---------------- |
| YYYY-MM-DD | 최초 작성        |
| YYYY-MM-DD |                  |

---

## 기타

(추가 설명/공지사항 등)
