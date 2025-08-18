import os
from pathlib import Path
from dotenv import load_dotenv

def load_environment_variables():
    """
    APP_ENV 환경 변수에 따라 .env.local 또는 .env.cloud 파일에서 환경 변수를 로드합니다.
    APP_ENV가 설정되지 않은 경우 기본적으로 .env.local을 사용합니다.
    """
    # APP_ENV 환경 변수를 확인하여 .env 파일 경로 결정 (기본값: 'local')
    env = os.getenv('APP_ENV', 'local')
    dotenv_path = Path(__file__).parent.parent / f".env.{env}"
    
    # 결정된 경로의 .env 파일 로드
    if dotenv_path.exists():
        load_dotenv(dotenv_path=dotenv_path)
        print(f"✅ '{dotenv_path.name}' 파일에서 환경 변수를 로드했습니다. (환경: {env})")
    else:
        # fallback으로 시스템 환경 변수만 사용하도록 경고 메시지 출력
        print(f"⚠️ {dotenv_path.name} 파일을 찾을 수 없습니다. 시스템에 설정된 환경 변수만 사용됩니다.")

# 함수 호출
load_environment_variables()

