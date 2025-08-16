@echo off

echo Starting FastAPI server...
start cmd /k "uvicorn main:app --host 0.0.0.0 --port 8080 --log-level debug --access-log --timeout-keep-alive 120"

echo Starting Streamlit server...
start cmd /k "streamlit run app.py --server.port 8501"

echo All servers started.