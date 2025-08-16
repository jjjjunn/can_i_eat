# import os
# import httpx
# from fastapi import APIRouter, Request, Depends, HTTPException
# from dotenv import load_dotenv
# from database.database import get_db_session
# from sqlalchemy.orm import Session
# from controllers.users_controllers import create_or_update_social_user
# from fastapi.responses import RedirectResponse
# import secrets
# import logging
# import requests

# load_dotenv()
# router = APIRouter()

# # 로깅 설정
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# KAKAO_AUTH_URL = "https://kauth.kakao.com/oauth/authorize"
# KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
# KAKAO_USERINFO_URL = "https://kapi.kakao.com/v2/user/me"

# KAKAO_CLIENT_ID = os.getenv("KAKAO_REST_API_KEY")
# KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET")
# KAKAO_REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI")

# STREAMLIT_APP_URL = os.getenv("STREAMLIT_APP_URL")

# @router.post("/auth/kakao/login")
# async def login(request: Request):
#     # CSRF 방지를 위한 state 토큰 생성
#     state = secrets.token_urlsafe(16)
#     request.session["oauth_state"] = state
#     logger.info(f"생성된 state: {state}") # 상태 정보 로그
#     logger.info(f"Session state stored: {request.session['oauth_state']}")  # state 값 저장 로그

#     auth_url = (
#         f"{KAKAO_AUTH_URL}?response_type=code"
#         f"&client_id={KAKAO_CLIENT_ID}"
#         f"&redirect_uri={KAKAO_REDIRECT_URI}"
#         f"&state={state}"
#     )
#     return RedirectResponse(url=auth_url)

# @router.get("/kakao/login/callback")
# async def kakao_login(request: Request, data: dict, db: Session = Depends(get_db_session)):
#     """Streamlit에서 보낸 인증 코드를 받아 카카오 로그인을 처리합니다."""
#     code = request.query_params.get("code")
#     state = request.query_params.get("state")
#     session_state = request.session.get("oauth_state")

#     # CSRF 방지: state 검증
#     logger.info(f"Session state: {session_state}, Callback state: {state}")  # 디버깅 로그
#     if state != session_state:
#         logger.warning("State Mismatch")
#         raise HTTPException(status_code=400, detail="Invalid OAuth State")
    
#     async with httpx.AsyncClient() as client:
#         token_res = await client.post(KAKAO_TOKEN_URL, data={
#             'code': code,
#             'client_id': KAKAO_CLIENT_ID,
#             'client_secret': KAKAO_CLIENT_SECRET,
#             'redirect_uri': KAKAO_REDIRECT_URI,
#             'grant_type': 'authorization_code',
#             'state': state,
#         })
        
#         if token_res.status_code != 200:
#             logger.error(f"Token 요청 실패: {token_res.status_code}: {token_res.text}")
#             return {"error": "Failed to retrieve token"}

#         token_data = token_res.json()
#         access_token = token_data.get("access_token")

#         # 사용자 정보 요청
#         userinfo_res = await client.get(KAKAO_USERINFO_URL, headers={
#             'Authorization': f'Bearer {access_token}'
#         })

#         if userinfo_res.status_code != 200:
#             logger.error(f"사용자 정보 요청 실패: {userinfo_res.text}")
#             return {"error": "Failed to retrieve user information"}

#         # 사용자 정보 처리
#         user_info_raw = userinfo_res.json()
#         kakao_id = str(user_info_raw.get("id"))
#         nickname = user_info_raw.get("properties", {}).get("nickname") or "User"
#         email = user_info_raw.get("kakao_account", {}).get("email")

#         # 필수 정보 확인
#         if not kakao_id or not nickname:
#             logger.error(f"유효하지 않은 사용자 정보: {user_info_raw}")
#             return {"error": "Invalid user info"}

#         user_info = {
#             "username": nickname,
#             "email": email,
#             "kakao_id": kakao_id, # 문자열로 형변환
#         }

#         user = create_or_update_social_user(db, user_info, provider='kakao', request=request, access_token=access_token)

#         # 로그인 후 세션에 정보 저장
#         request.session["id"] = user.id  # 일반 사용자 ID
#         request.session["name"] = user.name
#         request.session["provider_id"] = user.provider_id # ✅ user 객체에서 가져옴
#         request.session["provider"] = user.provider
#         request.session['access_token'] = access_token


#     # 로그인 성공 후 메인 페이지로 이동
#     redirect_url = f"{STREAMLIT_APP_URL}"
#     return RedirectResponse(url=redirect_url, status_code=303)















#     # code = data.get("code")
#     # redirect_uri = f"{os.getenv('API_URL')}/auth/kakao/callback"

#     # try:
#     #     # 1. 인증 코드를 사용하여 액세스 토큰 교환
#     #     token_url = KAKAO_TOKEN_URL
#     #     token_payload = {
#     #         "grant_type": "authorization_code",
#     #         "client_id": KAKAO_REST_API_KEY,
#     #         "client_secret": KAKAO_CLIENT_SECRET,
#     #         "redirect_uri": redirect_uri,
#     #         "code": code,
#     #     }
#     #     token_response = requests.post(token_url, data=token_payload)
#     #     token_response.raise_for_status()
#     #     access_token = token_response.json().get("access_token")

#     #     if not access_token:
#     #         raise HTTPException(status_code=400, detail="액세스 토큰을 얻지 못했습니다.")

#     #     # 2. 액세스 토큰으로 사용자 정보 가져오기
#     #     user_info_url = KAKAO_USERINFO_URL
#     #     user_info_response = requests.get(
#     #         user_info_url, 
#     #         headers={"Authorization": f"Bearer {access_token}"}
#     #     )
#     #     user_info_response.raise_for_status()
#     #     kakao_user_info = user_info_response.json()
        
#     #     # 카카오 사용자 정보 파싱
#     #     kakao_account = kakao_user_info.get("kakao_account", {})
#     #     profile = kakao_account.get("profile", {})

#     #     # 3. 새로운 User 모델에 맞게 사용자 정보 dict 생성
#     #     user_info_dict = {
#     #         "provider_id": str(kakao_user_info.get("id")),
#     #         "email": kakao_account.get("email"),
#     #         "name": profile.get("nickname"),
#     #     }

#     #     # 4. 사용자 정보로 DB에 저장 및 세션 처리
#     #     user = create_or_update_social_user(
#     #         db=db,
#     #         user_info=user_info_dict,
#     #         provider="kakao",
#     #         request=request,
#     #         access_token=access_token
#     #     )

#     #     # 5. 성공 응답 반환
#     #     return {"user_id": str(user.id), "username": user.name}

#     # except requests.exceptions.RequestException as e:
#     #     logger.error(f"카카오 로그인 API 요청 오류: {e}")
#     #     raise HTTPException(status_code=500, detail=f"카카오 로그인 중 오류가 발생했습니다: {e}")
#     # except Exception as e:
#     #     logger.error(f"카카오 로그인 처리 오류: {e}")
#     #     raise HTTPException(status_code=500, detail=f"로그인 처리 중 예기치 않은 오류가 발생했습니다: {e}")