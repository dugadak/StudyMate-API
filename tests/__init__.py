"""
StudyMate API 테스트 패키지

이 패키지는 프로젝트의 모든 테스트를 포함합니다.
- 단위 테스트 (Unit Tests)
- 통합 테스트 (Integration Tests)
- API 테스트 (API Tests)
- 성능 테스트 (Performance Tests)
"""

# 테스트 설정 확인
import os
import sys

# 테스트 환경인지 확인
if 'test' in sys.argv or 'pytest' in sys.modules:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'studymate_api.test_settings')
    print("🧪 테스트 환경으로 실행 중입니다.")