import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

def load_environment_variables():
    """환경 변수를 .env 파일과 env.yaml 파일에서 로드합니다."""
    # 먼저 .env 파일 로드
    load_dotenv()
    
    # env.yaml 파일이 있으면 로드
    env_yaml_path = Path(__file__).parent.parent / "env.yaml"
    if env_yaml_path.exists():
        try:
            with open(env_yaml_path, 'r', encoding='utf-8') as file:
                env_vars = yaml.safe_load(file)
                
            # 환경 변수로 설정 (이미 설정된 것은 덮어쓰지 않음)
            for key, value in env_vars.items():
                if key not in os.environ:
                    os.environ[key] = str(value)
                    
            print(f"✅ env.yaml에서 {len(env_vars)}개의 환경 변수를 로드했습니다.")
        except Exception as e:
            print(f"⚠️ env.yaml 로드 실패: {e}")
    else:
        print("⚠️ env.yaml 파일을 찾을 수 없습니다.")

