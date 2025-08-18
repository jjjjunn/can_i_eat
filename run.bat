@echo off
setlocal

REM 기본 환경을 local로 설정
set APP_ENV=local

REM 첫 번째 인자가 "cloud"이면 APP_ENV를 cloud로 변경
if /I "%1"=="cloud" (
    set APP_ENV=cloud
    echo Running in CLOUD mode.
) else (
    echo Running in LOCAL mode.
)

echo.
echo Setting APP_ENV=%APP_ENV%
echo.

echo Starting FastAPI server...
REM main.py가 APP_ENV를 읽어서 호스트/포트를 결정하므로 uvicorn 인자는 제거합니다.
start "FastAPI" cmd /k "python main.py"

echo.
echo Starting Streamlit server...
start "Streamlit" cmd /k "streamlit run app.py --server.port 8501"

echo.
echo All servers are starting in separate windows.

endlocal
