"""
테스트 전용 Django 설정

이 파일은 테스트 실행 시에만 사용되는 최적화된 설정을 제공합니다.
- 빠른 테스트 실행을 위한 설정
- 인메모리 데이터베이스 사용
- 캐시 및 미디어 파일 최적화
- 테스트 전용 서비스 설정
"""

from .settings import *

# 테스트용 간소화된 URL 설정
ROOT_URLCONF = 'studymate_api.test_urls'
import tempfile
import os
import sys
from datetime import timedelta

# 테스트 환경 표시
TESTING = True

# 디버그 모드 비활성화 (테스트 성능 향상)
DEBUG = False

# 테스트용 비밀 키 (보안이 중요하지 않음)
SECRET_KEY = 'test-secret-key-for-testing-only'

# 인메모리 SQLite 데이터베이스 사용 (빠른 테스트)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'OPTIONS': {
            'timeout': 20,
        }
    }
}

# 비동기 테스트를 위한 추가 데이터베이스 설정
if 'test' in sys.argv:
    DATABASES['default']['TEST'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }

# 캐시를 로컬 메모리로 설정 (빠른 테스트)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-cache',
        'TIMEOUT': 300,
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
            'CULL_FREQUENCY': 3,
        }
    }
}

# 이메일을 로컬 메모리에 저장 (테스트용)
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# 미디어 파일을 임시 디렉토리에 저장
MEDIA_ROOT = tempfile.mkdtemp()

# 정적 파일 설정 간소화
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# 로깅 최소화 (테스트 성능 향상)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'null': {
            'class': 'logging.NullHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['null'],
            'level': 'INFO',
        },
        'studymate_api': {
            'handlers': ['null'],
            'level': 'INFO',
        },
    }
}

# 비밀번호 해싱 최소화 (테스트 성능 향상)
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# 미들웨어 최소화
MIDDLEWARE = [
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

# Celery를 동기 모드로 설정 (테스트용)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# AI 서비스 모킹 설정
OPENAI_API_KEY = 'test-openai-key'
ANTHROPIC_API_KEY = 'test-anthropic-key'
TOGETHER_API_KEY = 'test-together-key'

# Stripe 테스트 키
STRIPE_PUBLISHABLE_KEY = 'pk_test_123'
STRIPE_SECRET_KEY = 'sk_test_123'
STRIPE_WEBHOOK_SECRET = 'whsec_test_123'

# 테스트 전용 설정
TEST_SETTINGS = {
    'MOCK_AI_SERVICES': True,
    'MOCK_PAYMENT_SERVICES': True,
    'MOCK_EMAIL_SERVICES': True,
    'SKIP_MIGRATIONS': True,
    'FAST_TESTS': True,
}

# 외부 서비스 비활성화
EXTERNAL_SERVICES = {
    'OPENAI_ENABLED': False,
    'STRIPE_ENABLED': False,
    'EMAIL_ENABLED': False,
    'NOTIFICATIONS_ENABLED': False,
}

# 고급 시스템들 비활성화 (테스트 성능 향상)
AUTO_RECOVERY_ENABLED = False
AB_TESTING_ENABLED = False
ZERO_TRUST_ENABLED = False
DISTRIBUTED_TRACING = {'ENABLED': False}
REALTIME_ANALYTICS = {'ENABLE_NOTIFICATIONS': False}

# 테스트 데이터 설정
TEST_DATA = {
    'DEFAULT_PASSWORD': 'testpass123',
    'ADMIN_EMAIL': 'admin@test.com',
    'USER_EMAIL': 'user@test.com',
    'SUBJECT_COUNT': 5,
    'QUIZ_COUNT': 10,
}

# JWT 설정 (테스트용 단기 토큰)
SIMPLE_JWT.update({
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=5),
    'REFRESH_TOKEN_LIFETIME': timedelta(minutes=10),
    'ROTATE_REFRESH_TOKENS': False,
})

# 스로틀링 비활성화 (테스트 속도 향상)
REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'] = []
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {}

# 권한 설정 간소화 (필요시 개별 테스트에서 오버라이드)
REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES'] = [
    'rest_framework.permissions.AllowAny',
]

# 테스트 실행 시 마이그레이션 최적화
if 'test' in sys.argv:
    # 마이그레이션 없이 테이블 생성
    class DisableMigrations:
        def __contains__(self, item):
            return True
        
        def __getitem__(self, item):
            return None
    
    if TEST_SETTINGS.get('SKIP_MIGRATIONS', False):
        MIGRATION_MODULES = DisableMigrations()

# 테스트 결과 디렉토리
TEST_RESULTS_DIR = os.path.join(BASE_DIR, 'test_results')
os.makedirs(TEST_RESULTS_DIR, exist_ok=True)

# 커버리지 설정
COVERAGE_SETTINGS = {
    'source': ['.'],
    'omit': [
        '*/venv/*',
        '*/migrations/*',
        '*/tests/*',
        'manage.py',
        '*/settings/*',
        '*/wsgi.py',
        '*/asgi.py',
    ],
    'exclude_lines': [
        'pragma: no cover',
        'def __repr__',
        'raise AssertionError',
        'raise NotImplementedError',
    ]
}

# pytest 설정
PYTEST_SETTINGS = {
    'DJANGO_SETTINGS_MODULE': 'studymate_api.test_settings',
    'addopts': [
        '--tb=short',
        '--strict-markers',
        '--disable-warnings',
        '--reuse-db',
        '--nomigrations',
    ],
    'testpaths': ['tests'],
    'python_files': ['test_*.py', '*_test.py'],
    'python_classes': ['Test*'],
    'python_functions': ['test_*'],
}

# 테스트 마커 정의
PYTEST_MARKERS = [
    'unit: 단위 테스트',
    'integration: 통합 테스트',
    'api: API 테스트',
    'slow: 느린 테스트',
    'auth: 인증 관련 테스트',
    'study: 학습 관련 테스트',
    'quiz: 퀴즈 관련 테스트',
    'subscription: 구독 관련 테스트',
    'notification: 알림 관련 테스트',
]

print(f"🧪 테스트 설정 로드됨 - 데이터베이스: {DATABASES['default']['ENGINE']}")