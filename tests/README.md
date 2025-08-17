# 🧪 StudyMate API 테스트 가이드

StudyMate API의 포괄적인 테스트 시스템에 대한 가이드입니다.

## 📋 목차

- [테스트 구조](#테스트-구조)
- [테스트 실행](#테스트-실행)
- [테스트 작성 가이드](#테스트-작성-가이드)
- [커버리지 리포트](#커버리지-리포트)
- [CI/CD 통합](#cicd-통합)

## 🏗️ 테스트 구조

### 테스트 타입

| 타입 | 설명 | 마커 | 목적 |
|------|------|------|------|
| **단위 테스트** | 개별 함수/클래스 테스트 | `@pytest.mark.unit` | 로직 검증 |
| **통합 테스트** | 컴포넌트 간 상호작용 | `@pytest.mark.integration` | 시스템 통합 검증 |
| **API 테스트** | REST API 엔드포인트 | `@pytest.mark.api` | API 동작 검증 |
| **성능 테스트** | 응답시간/리소스 사용량 | `@pytest.mark.performance` | 성능 요구사항 검증 |
| **보안 테스트** | 보안 취약점 검사 | `@pytest.mark.security` | 보안 검증 |

### 테스트 파일 구조

```
tests/
├── __init__.py                 # 테스트 패키지 초기화
├── utils.py                    # 테스트 유틸리티
├── factories.py                # Factory Boy 팩토리
├── test_accounts.py            # 계정 관련 테스트
├── test_study.py               # 학습 관련 테스트
├── test_quiz.py                # 퀴즈 관련 테스트
├── test_subscription.py        # 구독 관련 테스트
├── test_notifications.py       # 알림 관련 테스트
└── README.md                   # 이 파일
```

## 🚀 테스트 실행

### 기본 실행

```bash
# 모든 테스트 실행
python run_tests.py

# 또는 직접 pytest 사용
python -m pytest tests/
```

### 타입별 실행

```bash
# 단위 테스트만 실행
python run_tests.py --type unit

# 통합 테스트만 실행
python run_tests.py --type integration

# API 테스트만 실행
python run_tests.py --type api

# 성능 테스트만 실행
python run_tests.py --type performance

# 빠른 테스트 (느린 테스트 제외)
python run_tests.py --type fast
```

### 특정 앱 테스트

```bash
# accounts 앱 테스트
python run_tests.py --app accounts

# study 앱 테스트
python run_tests.py --app study
```

### 커버리지 포함 실행

```bash
# 커버리지 리포트와 함께 실행
python run_tests.py --coverage

# 상세 리포트 생성
python run_tests.py --report
```

### 고급 옵션

```bash
# 병렬 실행 (빠른 테스트)
python -m pytest tests/ -n 4

# 특정 테스트만 실행
python -m pytest tests/test_accounts.py::UserModelTest::test_create_user

# 키워드로 테스트 선택
python -m pytest tests/ -k "login"

# 실패한 테스트만 재실행
python -m pytest tests/ --lf

# 상세 출력
python -m pytest tests/ -v --tb=long
```

## ✍️ 테스트 작성 가이드

### 기본 테스트 클래스

```python
import pytest
from tests.utils import APITestCase, MockingTestCase
from tests.factories import UserFactory

@pytest.mark.unit
class MyModelTest(TestCase):
    """모델 단위 테스트"""
    
    def test_model_creation(self):
        # 테스트 로직
        pass

@pytest.mark.api
class MyAPITest(APITestCase):
    """API 테스트"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.authenticate_user(self.user)
    
    def test_api_endpoint(self):
        response = self.api_get('/api/endpoint/')
        self.assert_response_success(response)
```

### 팩토리 사용

```python
from tests.factories import UserFactory, SubjectFactory

# 기본 사용
user = UserFactory()

# 속성 오버라이드
admin = UserFactory(is_staff=True, is_superuser=True)

# 일괄 생성
subjects = SubjectFactory.create_batch(5)

# 관련 객체와 함께 생성
user, profile = create_test_user_with_profile()
```

### 모킹 사용

```python
class MyServiceTest(MockingTestCase):
    
    def test_external_service(self):
        # OpenAI 서비스 모킹
        self.mock_openai_service("테스트 응답")
        
        # Stripe 서비스 모킹
        self.mock_stripe_service()
        
        # 테스트 실행
        result = my_service.call_external_api()
        self.assertEqual(result, "테스트 응답")
```

### 성능 테스트

```python
@pytest.mark.performance
class PerformanceTest(APITestCase, PerformanceTestMixin):
    
    def test_api_performance(self):
        def api_call():
            return self.api_get('/api/endpoint/')
        
        # 응답 시간 검증 (1초 이내)
        self.assert_response_time(api_call, max_time_ms=1000)
        
        # 쿼리 수 검증 (5개 이하)
        self.assert_query_count(api_call, max_queries=5)
```

### 마커 사용

```python
@pytest.mark.unit
@pytest.mark.auth
def test_user_authentication():
    """사용자 인증 단위 테스트"""
    pass

@pytest.mark.integration
@pytest.mark.study
def test_study_workflow():
    """학습 워크플로우 통합 테스트"""
    pass

@pytest.mark.slow
@pytest.mark.external
def test_ai_service_integration():
    """AI 서비스 통합 테스트 (느림)"""
    pass
```

## 📊 커버리지 리포트

### 리포트 생성

```bash
# HTML 리포트 생성
python run_tests.py --coverage

# 리포트 확인
open test_results/coverage_html/index.html
```

### 커버리지 목표

| 컴포넌트 | 목표 커버리지 | 현재 상태 |
|----------|---------------|-----------|
| **전체** | 85% 이상 | 🎯 |
| **모델** | 90% 이상 | 🎯 |
| **뷰** | 80% 이상 | 🎯 |
| **서비스** | 85% 이상 | 🎯 |
| **시리얼라이저** | 85% 이상 | 🎯 |

### 커버리지 제외 항목

- 마이그레이션 파일
- 설정 파일
- 테스트 파일 자체
- `__repr__`, `__str__` 메서드
- 추상 메서드
- 개발 전용 코드

## 🔄 CI/CD 통합

### GitHub Actions

테스트는 다음 이벤트에서 자동 실행됩니다:

- `main` 브랜치에 푸시
- `develop` 브랜치에 푸시
- Pull Request 생성/업데이트

### 워크플로우 단계

1. **환경 설정** - Python, 의존성 설치
2. **코드 품질** - Black, Flake8, Bandit 검사
3. **단위 테스트** - 기본 로직 검증
4. **통합 테스트** - 시스템 통합 검증
5. **API 테스트** - 엔드포인트 검증
6. **성능 테스트** - 성능 요구사항 검증
7. **보안 테스트** - 보안 취약점 검사
8. **커버리지 업로드** - Codecov 연동

### 매트릭스 테스트

다음 환경에서 테스트됩니다:

- **Python**: 3.11, 3.12
- **Django**: 4.2, 5.0

## 🛠️ 테스트 도구

### 사용 중인 도구

| 도구 | 목적 | 설정 파일 |
|------|------|-----------|
| **pytest** | 테스트 실행기 | `pytest.ini` |
| **pytest-django** | Django 통합 | `pytest.ini` |
| **pytest-cov** | 커버리지 측정 | `.coveragerc` |
| **Factory Boy** | 테스트 데이터 생성 | `factories.py` |
| **Faker** | 더미 데이터 생성 | `factories.py` |
| **pytest-mock** | 모킹 | `utils.py` |
| **pytest-xdist** | 병렬 실행 | CLI |
| **pytest-benchmark** | 벤치마킹 | CLI |

### 설정 파일

- **`pytest.ini`** - pytest 기본 설정
- **`.coveragerc`** - 커버리지 설정
- **`studymate_api/test_settings.py`** - 테스트용 Django 설정

## 🎯 베스트 프랙티스

### 테스트 작성 원칙

1. **AAA 패턴** - Arrange, Act, Assert
2. **독립성** - 테스트 간 의존성 없이
3. **명확성** - 테스트 의도가 명확하게
4. **신속성** - 빠른 실행을 위해
5. **신뢰성** - 일관된 결과 보장

### 네이밍 컨벤션

```python
# 좋은 예
def test_user_login_with_valid_credentials_returns_success():
    pass

def test_create_study_summary_without_authentication_returns_401():
    pass

# 나쁜 예
def test_login():
    pass

def test_summary():
    pass
```

### 데이터 관리

```python
# 팩토리 사용 (권장)
user = UserFactory(email='test@example.com')

# 직접 생성 (지양)
user = User.objects.create(
    email='test@example.com',
    password='test123'
)
```

## 🚨 문제 해결

### 일반적인 문제

1. **ImportError**: Django 설정 확인
2. **Database Error**: 테스트 DB 권한 확인
3. **Slow Tests**: 불필요한 DB 접근 최소화
4. **Flaky Tests**: 시간 의존적 코드 모킹

### 디버깅 팁

```bash
# 디버깅 모드로 실행
python -m pytest tests/ --pdb

# 출력 확인
python -m pytest tests/ -s

# 특정 테스트만 실행
python -m pytest tests/test_accounts.py::test_login -v
```

## 📞 지원

- **이슈 리포팅**: GitHub Issues
- **문의사항**: 개발팀 Slack 채널
- **문서 업데이트**: PR 환영

---

**마지막 업데이트**: 2024년 1월  
**버전**: 1.0.0