@echo off
setlocal

REM Set the default environment to local
set APP_ENV=local

REM If the first argument is "cloud", change APP_ENV to cloud
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
start "FastAPI (%APP_ENV%)" cmd /k "python main.py"

echo.
echo Starting Streamlit server...
start "Streamlit" cmd /k "streamlit run app.py --server.port 8501"

echo.
echo All servers are starting in separate windows.

endlocal