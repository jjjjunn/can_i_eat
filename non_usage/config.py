# from fastapi import Request, Depends, HTTPException, APIRouter, HTMLResponse
# import os
# from pydantic import BaseSettings

# router = APIRouter()

# class Settings(BaseSettings):
#     # OAuth 설정
#     GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID")
#     GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET")
#     NAVER_CLIENT_ID: str = os.getenv("NAVER_CLIENT_ID")
#     NAVER_CLIENT_SECRET: str = os.getenv("NAVER_CLIENT_SECRET")
    
#     # 서버 설정
#     SERVER_HOST: str = "localhost"
#     SERVER_PORT: int = 8000
    
#     # 환경별 Redirect URI
#     @property
#     def GOOGLE_REDIRECT_URI(self):
#         return f"http://{self.SERVER_HOST}:{self.SERVER_PORT}/auth/google/callback"
    
#     @property
#     def NAVER_REDIRECT_URI(self):
#         return f"http://{self.SERVER_HOST}:{self.SERVER_PORT}/auth/naver/callback"

# settings = Settings()

# # OAuth 라우터에서 사용
# from authlib.integrations.requests_client import OAuth2Session

# def create_google_oauth_session():
#     return OAuth2Session(
#         client_id=settings.GOOGLE_CLIENT_ID,
#         client_secret=settings.GOOGLE_CLIENT_SECRET,
#         redirect_uri=settings.GOOGLE_REDIRECT_URI,
#         scope="openid email profile"
#     )

# # 로그인 상태 확인 API
# @router.get("/auth/status")
# def get_auth_status(request: Request):
#     """현재 로그인 상태 확인"""
#     if request.session.get('is_logged_in'):
#         return {
#             "logged_in": True,
#             "user_id": request.session.get('id'),
#             "name": request.session.get('name'),
#             "provider": request.session.get('provider')
#         }
#     return {"logged_in": False}

# # 로그아웃 API
# @router.post("/auth/logout")
# def logout(request: Request):
#     """로그아웃 처리"""
#     request.session.clear()
#     return {"message": "로그아웃되었습니다"}

# # 로그인 성공 후 창 닫기 HTML
# LOGIN_SUCCESS_HTML = """
# <!DOCTYPE html>
# <html>
# <head>
#     <title>로그인 성공</title>
# </head>
# <body>
#     <script>
#         // 부모 창에 성공 메시지 전달
#         if (window.opener) {
#             window.opener.postMessage('login_success', '*');
#         }
#         // 현재 창 닫기
#         window.close();
        
#         // 창이 닫히지 않으면 리디렉션
#         setTimeout(function() {
#             window.location.href = '/';
#         }, 1000);
#     </script>
#     <h2>로그인 성공!</h2>
#     <p>창이 자동으로 닫힙니다...</p>
# </body>
# </html>
# """

# @router.get("/auth/success")
# def login_success():
#     """로그인 성공 페이지"""
#     return HTMLResponse(content=LOGIN_SUCCESS_HTML)