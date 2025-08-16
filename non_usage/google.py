# import os
# import httpx
# from fastapi import APIRouter, Request, Depends, HTTPException
# from dotenv import load_dotenv
# from database.database import get_db_session
# from sqlalchemy.orm import Session
# from controllers.users_controllers import create_or_update_social_user
# from fastapi.responses import RedirectResponse
# import requests
# import secrets
# import logging

# load_dotenv()
# router = APIRouter()

# # 로깅 설정
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
# GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
# GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"

# GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
# GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
# GOOGLE_REDIRECT_URI= os.getenv("GOOGLE_REDIRECT_URI")

# STREAMLIT_APP_URL = os.getenv("STREAMLIT_APP_URL")


# @router.get("/auth/google/login")
# async def login(request: Request):
#     # CSRF 방지를 위한 state 토큰 생성
#     state = secrets.token_urlsafe(16)
#     request.session["oauth_state"] = state
#     logger.info(f"생성된 state: {state}") # 상태 정보 로그
#     logger.info(f"Session state stored: {request.session['oauth_state']}")  # state 값 저장 로그

#     auth_url = (
#         f"{GOOGLE_AUTH_URL}?response_type=code"
#         f"&client_id={GOOGLE_CLIENT_ID}"
#         f"&redirect_uri={GOOGLE_REDIRECT_URI}"
#         f"&scope=openid%20email%20profile"
#         f"&access_type=offline"
#         f"&prompt=consent"
#         f"&state={state}"
#     )
#     return RedirectResponse(url=auth_url)


# @router.get("/auth/google/callback")
# async def google_callback(request: Request, data: dict, db: Session = Depends(get_db_session)):
#     """Streamlit에서 보낸 인증 코드를 받아 구글 로그인을 처리합니다."""
    
#     code = request.query_params.get("code")
#     state = request.query_params.get("state")
#     session_state = request.session.get("oauth_state")
    
#      # CSRF 방지: state 검증
#     logger.info(f"Session state: {session_state}, Callback state: {state}")  # 디버깅 로그
#     if state != session_state:
#         logger.warning("State Mismatch")
#         raise HTTPException(status_code=400, detail="Invalid OAuth State")
    
#     async with httpx.AsyncClient() as client:
#         token_res = await client.post(GOOGLE_TOKEN_URL, data={
#             'code': code,
#             'client_id': GOOGLE_CLIENT_ID,
#             'client_secret': GOOGLE_CLIENT_SECRET,
#             'redirect_uri': GOOGLE_REDIRECT_URI,
#             'grant_type': 'authorization_code',
#         }) # 'state': state, 구글 토큰에 요청 불가
    
#     if token_res.status_code != 200:
#             logger.error(f"Token 요청 실패: {token_res.status_code}: {token_res.text}")
#             return {"error": "Failed to retrieve token"}

#     token_data = token_res.json()
#     access_token = token_data.get("access_token")
    
#     # 사용자 정보 요청
#     userinfo_res = await client.get(GOOGLE_USERINFO_URL, headers={
#         'Authorization': f'Bearer {access_token}'
#     })

#     if userinfo_res.status_code != 200:
#         logger.error(f"사용자 정보 요청 실패: {userinfo_res.text}")
#         return {"error": "Failed to retrieve user information"}

#     # 사용자 정보 처리
#     user_info_raw = userinfo_res.json()
#     google_id = str(user_info_raw.get("id"))
#     username = user_info_raw.get("name") or "User" # 이름이 없을 경우 기본값 설정
#     email = user_info_raw.get("email")

#     # 필수 정보 확인
#     if not google_id or not username:
#         logger.error(f"유효하지 않은 사용자 정보: {user_info_raw}")
#         return {"error": "Invalid user info"}
    
#     user_info = {
#         "username" : username,  
#         "email" : email,
#         "google_id" : google_id,
#     }

#     user = create_or_update_social_user(db, user_info, 'google', access_token) 

#     # 로그인 후 세션에 정보 저장 (User 모델 속성 이름과 일치시킴)
#     request.session["id"] = user.id
#     request.session["name"] = user.name # ✅ name으로 통일
#     request.session["provider_id"] = user.provider_id # ✅ user 객체에서 가져옴
#     request.session["provider"] = user.provider
#     request.session['access_token'] = access_token

#     # 로그인 성공 후 메인 페이지로 이동
#     redirect_url = f"{STREAMLIT_APP_URL}/app"
#     return RedirectResponse(url=redirect_url, status_code=303)
    
#     # if not code:
#     #     raise ValueError("인가 코드가 없습니다.")
    
#     # redirect_uri = f"{os.getenv('API_URL')}/auth/google/callback"

#     # try:
#     #     # 1. 인증 코드를 사용하여 액세스 토큰 교환
#     #     token_url = GOOGLE_TOKEN_URL
#     #     token_payload = {
#     #         "code": code,
#     #         "client_id": GOOGLE_CLIENT_ID,
#     #         "client_secret": GOOGLE_CLIENT_SECRET,
#     #         "redirect_uri": redirect_uri,
#     #         "grant_type": "authorization_code",
#     #     }
#     #     token_response = requests.post(token_url, data=token_payload)
#     #     token_response.raise_for_status()
#     #     access_token = token_response.json().get("access_token")

#     #     if not access_token:
#     #         raise HTTPException(status_code=400, detail="액세스 토큰을 얻지 못했습니다.")

#     #     # 2. 액세스 토큰으로 사용자 정보 가져오기
#     #     user_info_url = GOOGLE_USERINFO_URL
#     #     user_info_response = requests.get(user_info_url, headers={"Authorization": f"Bearer {access_token}"})
#     #     user_info_response.raise_for_status()
#     #     google_user_info = user_info_response.json()
        
#     #     # 3. 새로운 User 모델에 맞게 사용자 정보 dict 생성
#     #     user_info_dict = {
#     #         "provider_id": google_user_info.get("sub"),
#     #         "email": google_user_info.get("email"),
#     #         "name": google_user_info.get("name"),
#     #     }

#     #     # 4. 사용자 정보로 DB에 저장 및 세션 처리
#     #     user = create_or_update_social_user(
#     #         db=db,
#     #         user_info=user_info_dict,
#     #         provider="google",
#     #         request=request,
#     #         access_token=access_token
#     #     )
        
#     #     # 5. 성공 응답 반환
#     #     return {"user_id": str(user.id), "username": user.name}

#     # except requests.exceptions.RequestException as e:
#     #     logger.error(f"구글 로그인 API 요청 오류: {e}")
#     #     raise HTTPException(status_code=500, detail=f"구글 로그인 중 오류가 발생했습니다: {e}")
#     # except Exception as e:
#     #     logger.error(f"구글 로그인 처리 오류: {e}")
#     #     raise HTTPException(status_code=500, detail=f"로그인 처리 중 예기치 않은 오류가 발생했습니다: {e}")