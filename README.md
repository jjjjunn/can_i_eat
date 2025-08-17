# 🤰 먹어도 돼? - 임산부를 위한 AI 성분 분석 서비스

**"이거, 임신 중에 먹어도 괜찮을까?"**  
세상 모든 예비 엄마들의 작은 걱정을 덜어주기 위해 시작된 프로젝트입니다. 음식 성분표 이미지를 찍어 올리기만 하면, AI가 임신부에게 안전하지 않은 성분이 있는지 분석하고 섭취 가이드를 제공합니다.

[![GCP Cloud Run](https://img.shields.io/badge/Deploy-GCP%20Cloud%20Run-4285F4?style=for-the-badge&logo=googlecloud)](https://cloud.google.com/run)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Frontend-Streamlit-FF4B4B?style=for-the-badge&logo=streamlit)](https://streamlit.io/)
[![Google Gemini](https://img.shields.io/badge/AI-Google%20Gemini-8E75B9?style=for-the-badge&logo=google&logoColor=white)](https://ai.google/discover/gemini/)

---

## 🌟 주요 기능

- **📸 이미지 속 성분 자동 추출 (OCR)**
  - 스마트폰으로 찍은 어떤 형태의 성분표 이미지든 Google Cloud Vision AI의 강력한 OCR 기술로 텍스트를 정확하게 인식하고 추출합니다.
- **🤖 AI 기반 섭취 가능 여부 분석**
  - 추출된 성분 목록을 Google Gemini Pro 모델이 분석하여, 임신부에게 잠재적으로 해로울 수 있는 성분을 식별하고 상세한 섭취 가이드를 제공합니다.
  - 논문, 전문 자료 등 신뢰도 높은 정보를 기반으로 답변을 생성하는 **RAG(Retrieval-Augmented Generation)** 기술을 적용하여 AI 답변의 정확성과 신뢰도를 높였습니다.
- **🔐 간편하고 안전한 소셜 로그인**
  - Google, Kakao 계정을 사용한 OAuth 2.0 기반 소셜 로그인을 지원하여, 사용자가 별도의 회원가입 없이 안전하고 편리하게 서비스를 이용할 수 있습니다.
- **📚 나만의 분석 기록 관리**
  - 사용자가 분석했던 모든 기록은 이미지와 함께 계정에 안전하게 저장됩니다.
  - 언제든지 과거 분석 기록을 다시 확인하고, 필요 없는 기록은 삭제할 수 있습니다.

---

## 🏛️ 시스템 아키텍처

이 서비스는 확장성과 안정성을 고려하여 **FastAPI 기반의 백엔드 API 서버**와 **Streamlit 기반의 프론트엔드 웹 앱**으로 분리하여 설계되었습니다. 모든 서비스는 Docker 컨테이너화되어 GCP Cloud Run을 통해 서버리스 환경에서 효율적으로 운영됩니다.

```
[ 사용자 (웹 브라우저) ]
       |
       v
[ Streamlit Frontend (GCP Cloud Run) ] <--- (인증: OAuth 2.0, JWT)
       |
       |  (REST API 요청)
       v
[ FastAPI Backend (GCP Cloud Run) ]
       |
       +-----> [ Google Cloud Vision AI ] (OCR 요청)
       |
       +-----> [ Google Gemini Pro ] (AI 분석 요청)
       |
       +-----> [ Google Cloud SQL (PostgreSQL) ] (사용자 정보, 분석 기록 CRUD)
       |
       +-----> [ Google Cloud Storage ] (업로드된 이미지 저장/조회)
```

---

## 🛠️ 기술 스택

| 구분         | 기술 / 서비스                                                              | 목적                               |
| :----------- | :------------------------------------------------------------------------- | :--------------------------------- |
| **Backend**  | `FastAPI`, `Python 3.12`, `Uvicorn`                                        | REST API 서버 구축                 |
| **Frontend** | `Streamlit`                                                                | 데이터 앱 프레임워크, UI/UX 구현   |
| **Database** | `PostgreSQL (GCP Cloud SQL)`, `SQLModel`, `SQLAlchemy`                     | 데이터 영속성, 사용자 및 로그 관리 |
| **AI & OCR** | `Google Gemini Pro`, `Google Cloud Vision AI`, `LangChain (RAG)`           | AI 분석, OCR, 답변 신뢰도 향상     |
| **Infra**    | `GCP Cloud Run`, `Docker`, `Nginx`, `Supervisor`                           | 서버리스 배포, 컨테이너화, 프로세스 관리 |
| **Storage**  | `GCP Cloud Storage`                                                        | 이미지 파일 등 정적 자원 저장      |
| **Auth**     | `OAuth 2.0 (Google, Kakao)`, `JWT`                                         | 소셜 로그인, API 인증/인가         |

---

## 💡 기술적 도전과 배운 점

### 1. AI 답변의 신뢰성 확보 (Hallucination 문제 해결)
- **문제점:** Gemini와 같은 LLM은 때때로 사실이 아닌 정보를 생성하는 '환각(Hallucination)' 현상을 보입니다. 특히 임산부의 건강과 직결된 민감한 정보를 다루기 때문에, 답변의 신뢰성 확보가 가장 중요한 과제였습니다.
- **해결 과정:**
  - **RAG (Retrieval-Augmented Generation) 아키텍처 도입:** 신뢰할 수 있는 논문, 의학 정보 PDF 자료들을 벡터 데이터베이스(FAISS)로 구축했습니다.
  - 사용자의 질문과 관련된 정보를 먼저 이 DB에서 검색(Retrieval)한 후, 검색된 내용을 컨텍스트로 함께 Gemini 모델에 전달하여 답변을 생성(Generation)하도록 파이프라인을 설계했습니다.
  - 이를 통해 AI가 자체적으로 부정확한 정보를 생성하는 것을 최소화하고, 검증된 자료에 기반한 답변을 제공하도록 유도하여 서비스의 신뢰도를 크게 향상시킬 수 있었습니다.

### 2. 프론트엔드-백엔드 간 안전한 인증 상태 유지
- **문제점:** Streamlit은 상태 비저장(Stateless) 특성을 가지므로, 페이지 이동 시 로그인 상태를 유지하고 백엔드 API에 안전하게 인증 정보를 전달하는 것이 복잡했습니다.
- **해결 과정:**
  - **OAuth 2.0과 JWT 토큰 통합:** 소셜 로그인 성공 후, FastAPI 백엔드에서 JWT(JSON Web Token)를 발급하여 프론트엔드로 전달합니다.
  - Streamlit의 `st.session_state`와 쿠키를 활용하여 JWT 토큰을 안전하게 저장하고, 페이지가 재실행될 때마다 로그인 상태를 복원합니다.
  - 백엔드 API 호출 시에는 HTTP 헤더에 JWT를 담아 전송하고, FastAPI는 이를 검증하여 사용자를 인가하는 방식으로 안전한 통신을 구현했습니다.

---

## 🚀 설치 및 실행 방법

### 1. 프로젝트 클론
```bash
git clone https://github.com/your-username/can_i_eat_st.git
cd can_i_eat_st
```

### 2. 가상환경 생성 및 패키지 설치
```bash
# Python 가상환경 생성 및 활성화
python -m venv venv
# Windows
# venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# 필수 패키지 설치
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. 환경 변수 설정
프로젝트 루트 디렉토리에 있는 `.env.example` 파일을 `.env` 파일로 복사한 후, 본인의 환경에 맞게 값을 수정합니다.
```bash
cp .env.example .env
# 이후 .env 파일을 에디터로 열어 값을 수정합니다.
```

### 4. 데이터베이스 테이블 생성
FastAPI 서버를 처음 실행하기 전에, DB에 필요한 테이블들을 생성해야 합니다.
```bash
python -c "from database.database import create_db_and_tables; create_db_and_tables()"
```

### 5. 서버 실행
두 개의 터미널을 열고, 각각 백엔드 서버와 프론트엔드 앱을 실행합니다.

- **터미널 1: FastAPI 백엔드 서버 실행**
  ```bash
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
  ```

- **터미널 2: Streamlit 프론트엔드 앱 실행**
  ```bash
  streamlit run app.py
  ```

이제 웹 브라우저에서 `http://localhost:8501` 주소로 접속하여 서비스를 확인할 수 있습니다.

---

## 📖 API Endpoints

FastAPI 백엔드는 다음과 같은 주요 API 엔드포인트를 제공합니다. (상세 내용은 `/docs` 참조)

| Method | Path                           | 설명                               |
| :----- | :----------------------------- | :--------------------------------- |
| `POST` | `/analyze/ocr/`                | 이미지 파일로 성분을 추출합니다.   |
| `POST` | `/analyze/chatbot/`            | 성분 목록으로 AI 분석을 요청합니다.|
| `GET`  | `/users/{user_id}/logs/`       | 특정 사용자의 모든 분석 기록을 조회합니다. |
| `GET`  | `/users/{user_id}/logs/{log_id}/` | 특정 분석 기록을 상세 조회합니다. |
| `DELETE`| `/users/{user_id}/logs/{log_id}/` | 특정 분석 기록을 삭제합니다.       |
| `GET`  | `/auth/{provider}/login`       | 소셜 로그인 (Google/Kakao)을 시작합니다. |
| `GET`  | `/auth/{provider}/callback`    | 소셜 로그인 콜백을 처리합니다.     |

---

## 📝 향후 개선 계획

- [ ] **성분 정보 DB화:** 자주 분석되는 성분과 그에 대한 분석 결과를 DB에 저장하여, 반복적인 AI 호출을 줄이고 응답 속도를 개선합니다.
- [ ] **관리자 대시보드:** 서비스 이용 통계, 사용자 관리 등 관리자 전용 기능을 고도화합니다.
- [ ] **테스트 코드 작성:** `pytest` 등을 활용하여 API의 안정성과 코드 품질을 높입니다.
- [ ] **CI/CD 파이프라인 구축:** `cloudbuild.yaml`을 고도화하여 Git push 시 자동으로 테스트, 빌드, 배포가 이루어지도록 자동화합니다.