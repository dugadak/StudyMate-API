# 개발 가이드

## 🎯 개발 환경 설정

### 필수 요구사항
- **Python**: 3.10+
- **Django**: 5.2+
- **PostgreSQL**: 14+
- **Redis**: 7+
- **Node.js**: 18+ (프론트엔드 도구용)

### 로컬 환경 구성

```bash
# 1. 저장소 클론
git clone https://github.com/StudyMate-ComPany/StudyMate-API.git
cd StudyMate-API

# 2. 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 환경변수 설정
cp .env.example .env
# .env 파일을 편집하여 필요한 값들 설정

# 5. 데이터베이스 설정
python manage.py migrate
python manage.py collectstatic

# 6. 슈퍼유저 생성
python manage.py createsuperuser

# 7. 개발 서버 실행
python manage.py runserver
```

### 환경변수 설정

`.env` 파일 예시:
```bash
# Django 설정
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# 데이터베이스
DATABASE_URL=postgresql://user:password@localhost:5432/studymate
REDIS_URL=redis://localhost:6379/0

# 외부 API 키
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
TOGETHER_API_KEY=your-together-api-key

# 결제 시스템
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# 모니터링
SENTRY_DSN=https://...
```

## 🏗 프로젝트 구조

```
StudyMate-API/
├── accounts/              # 사용자 인증 및 프로필 관리
├── study/                 # 학습 관련 기능
├── quiz/                  # 퀴즈 시스템
├── subscription/          # 구독 및 결제
├── notifications/         # 알림 시스템
├── studymate_api/         # 메인 Django 설정
│   ├── settings.py        # 기본 설정
│   ├── test_settings.py   # 테스트 설정
│   ├── urls.py            # URL 라우팅
│   ├── middleware/        # 커스텀 미들웨어
│   ├── management/        # Django 관리 명령어
│   └── views/             # 공통 뷰
├── docs/                  # 프로젝트 문서
├── tests/                 # 테스트 파일
├── .github/               # GitHub Actions 워크플로
└── docker/                # Docker 설정 파일
```

## 📝 코딩 컨벤션

### Python 스타일 가이드

**Black 포매터 사용**:
```python
# Good
def create_user_profile(user_id: int, profile_data: Dict[str, Any]) -> UserProfile:
    """사용자 프로필을 생성합니다."""
    return UserProfile.objects.create(
        user_id=user_id,
        **profile_data
    )

# 함수명: snake_case
# 클래스명: PascalCase
# 상수명: UPPER_SNAKE_CASE
```

### Django 베스트 프랙티스

**모델 정의**:
```python
class StudySession(TimeStampedModel):
    """학습 세션 모델"""
    
    class Meta:
        db_table = 'study_session'
        ordering = ['-created_at']
        
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='study_sessions'
    )
    
    def __str__(self) -> str:
        return f"{self.user.email} - {self.created_at}"
```

**뷰 클래스**:
```python
class StudySessionViewSet(ModelViewSet):
    """학습 세션 API"""
    
    queryset = StudySession.objects.all()
    serializer_class = StudySessionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    
    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)
```

### API 설계 원칙

**RESTful API 구조**:
```
GET    /api/v1/study/sessions/     # 목록 조회
POST   /api/v1/study/sessions/     # 생성
GET    /api/v1/study/sessions/1/   # 상세 조회
PUT    /api/v1/study/sessions/1/   # 전체 수정
PATCH  /api/v1/study/sessions/1/   # 부분 수정
DELETE /api/v1/study/sessions/1/   # 삭제
```

**응답 형식 표준화**:
```python
# 성공 응답
{
    "success": true,
    "data": {
        "id": 1,
        "title": "Python 기초 학습",
        "duration": 3600
    },
    "message": "학습 세션이 성공적으로 생성되었습니다."
}

# 에러 응답
{
    "success": false,
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "입력 데이터가 유효하지 않습니다.",
        "details": {
            "title": ["이 필드는 필수입니다."]
        }
    }
}
```

## 🧪 테스트 작성

### 테스트 구조

```python
# tests/test_study.py
import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User
from study.models import StudySession


@pytest.mark.django_db
class TestStudySessionAPI:
    """학습 세션 API 테스트"""
    
    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    def test_create_study_session_success(self):
        """학습 세션 생성 성공 테스트"""
        url = reverse('study:session-list')
        data = {
            'title': 'Python 기초',
            'duration': 3600,
            'subject_id': 1
        }
        
        response = self.client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert StudySession.objects.filter(user=self.user).exists()
    
    @pytest.mark.parametrize('field,value', [
        ('title', ''),
        ('duration', -1),
        ('subject_id', None)
    ])
    def test_create_study_session_validation_error(self, field, value):
        """학습 세션 생성 유효성 검사 테스트"""
        url = reverse('study:session-list')
        data = {
            'title': 'Python 기초',
            'duration': 3600,
            'subject_id': 1
        }
        data[field] = value
        
        response = self.client.post(url, data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
```

### 테스트 실행

```bash
# 전체 테스트
pytest

# 특정 앱 테스트
pytest accounts/

# 커버리지 포함
pytest --cov=. --cov-report=html

# 특정 마커 테스트만
pytest -m "not slow"

# 병렬 실행
pytest -n auto
```

## 🔧 개발 도구

### 사전 커밋 훅

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black
        language_version: python3.10

  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort

  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
```

### VS Code 설정

`.vscode/settings.json`:
```json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.formatting.provider": "black",
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.testing.pytestEnabled": true,
    "files.associations": {
        "*.html": "django-html"
    }
}
```

## 🚀 배포 가이드

### Docker를 이용한 배포

```dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "studymate_api.wsgi:application"]
```

### Kubernetes 배포

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: studymate-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: studymate-api
  template:
    metadata:
      labels:
        app: studymate-api
    spec:
      containers:
      - name: api
        image: studymate/api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: studymate-secrets
              key: database-url
```

## 🔍 디버깅 가이드

### 로깅 설정

```python
# settings.py
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        }
    },
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {name} {message}',
            'style': '{'
        }
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO'
        },
        'studymate_api': {
            'handlers': ['console'],
            'level': 'DEBUG'
        }
    }
}
```

### 디버깅 도구

```python
# Django Debug Toolbar (개발환경)
if DEBUG:
    import debug_toolbar
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')

# Django Extensions
INSTALLED_APPS += ['django_extensions']

# 셸 플러스 사용
python manage.py shell_plus --ipython
```

## 📊 모니터링 및 성능

### 성능 최적화

**데이터베이스 쿼리 최적화**:
```python
# N+1 문제 해결
queryset = StudySession.objects.select_related('user', 'subject')
queryset = StudySession.objects.prefetch_related('quiz_attempts')

# 인덱스 추가
class Meta:
    indexes = [
        models.Index(fields=['user', 'created_at']),
        models.Index(fields=['subject', 'status'])
    ]
```

**캐싱 전략**:
```python
from django.core.cache import cache

def get_user_study_stats(user_id):
    cache_key = f'user_study_stats:{user_id}'
    stats = cache.get(cache_key)
    
    if stats is None:
        stats = calculate_study_stats(user_id)
        cache.set(cache_key, stats, timeout=3600)
    
    return stats
```

## 🤝 기여 가이드

### 기여 프로세스

1. **이슈 생성**: 새로운 기능이나 버그 리포트
2. **브랜치 생성**: `feature/기능명` 또는 `fix/버그명`
3. **코드 작성**: 컨벤션 준수 및 테스트 포함
4. **Pull Request**: 리뷰 요청 및 CI 검사 통과
5. **코드 리뷰**: 팀원 리뷰 및 피드백 반영
6. **머지**: 승인 후 메인 브랜치에 병합

### 커밋 메시지 가이드

```
<type>(<scope>): <subject>

<body>

<footer>
```

**예시**:
```
feat(study): add real-time progress tracking

- Implement WebSocket connection for live updates
- Add progress calculation algorithms
- Include user engagement metrics

Closes #123
```

**타입**:
- `feat`: 새로운 기능
- `fix`: 버그 수정
- `docs`: 문서 변경
- `style`: 코드 포매팅
- `refactor`: 코드 리팩토링
- `test`: 테스트 추가/수정
- `chore`: 빌드/배포 관련

---

**마지막 업데이트**: 2025년 8월 19일  
**담당자**: StudyMate 개발팀  
**버전**: v2.0.0