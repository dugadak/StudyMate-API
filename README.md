# StudyMate API Server

> StudyMate 서비스의 백엔드 API 서버

AI 기반 개인화 학습 플랫폼 StudyMate의 서버 사이드 애플리케이션입니다. Django REST Framework를 기반으로 구축되었으며, OpenAI GPT를 활용한 개인화 학습 콘텐츠 생성 및 Stripe 결제 시스템을 제공합니다.

## 🏗️ 서버 아키텍처

### 시스템 구성도
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Mobile App    │    │   Web Client    │    │   Admin Panel   │
│  (React Native) │    │     (React)     │    │  (Django Admin) │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────────┐
                    │  API Gateway    │
                    │ (Load Balancer) │
                    └─────────┬───────┘
                              │
                    ┌─────────────────┐
                    │  Django Server  │
                    │   (REST API)    │
                    └─────────┬───────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼────────┐  ┌────────▼────────┐  ┌────────▼────────┐
│   PostgreSQL   │  │   Redis Cache   │  │   Celery Queue  │
│   (Database)   │  │   (Session)     │  │  (Background)   │
└────────────────┘  └─────────────────┘  └─────────────────┘
                              │
                    ┌─────────▼───────┐
                    │  External APIs  │
                    │ OpenAI, Stripe  │
                    └─────────────────┘
```

### 주요 서버 컴포넌트

- 🔐 **인증 시스템**: Django Token Authentication
- 📚 **학습 관리**: 개인화 설정 및 진도 추적
- 🤖 **AI 엔진**: OpenAI GPT 통합 서비스
- 📝 **퀴즈 엔진**: 문제 생성 및 채점 시스템
- 🔔 **알림 서버**: Celery 기반 스케줄링
- 💳 **결제 처리**: Stripe 웹훅 및 구독 관리

## 🛠️ 기술 스택

### **Backend Framework**
- **Django 5.2**: 웹 프레임워크
- **Django REST Framework 3.16**: REST API 개발
- **Python 3.10+**: 프로그래밍 언어

### **Database & Cache**
- **PostgreSQL**: 프로덕션 데이터베이스
- **SQLite**: 개발환경 데이터베이스
- **Redis**: 캐싱 및 세션 스토어

### **External Services**
- **OpenAI GPT-3.5/4**: AI 콘텐츠 생성
- **Stripe**: 결제 처리 및 구독 관리
- **Firebase**: 푸시 알림 (예정)

### **Background Processing**
- **Celery**: 비동기 작업 처리
- **Redis**: 메시지 브로커

### **Development & Deployment**
- **Docker**: 컨테이너화
- **GitHub Actions**: CI/CD
- **AWS/GCP**: 클라우드 인프라 (예정)

### **Monitoring & Documentation**
- **drf-spectacular**: Swagger/OpenAPI 문서
- **Django Debug Toolbar**: 개발용 디버깅
- **Sentry**: 에러 모니터링 (예정)

## 📦 설치 및 실행

### 요구사항

- Python 3.10+
- Redis (알림 및 Celery용)

### 설치

1. **저장소 클론**
```bash
git clone <repository-url>
cd StudyMate-API
```

2. **가상환경 생성 및 활성화**
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

3. **패키지 설치**
```bash
pip install -r requirements.txt
```

4. **환경변수 설정**
```bash
cp .env.example .env
# .env 파일에서 필요한 값들 설정
```

5. **데이터베이스 마이그레이션**
```bash
python manage.py migrate
```

6. **관리자 계정 생성**
```bash
python manage.py createsuperuser
```

7. **서버 실행**
```bash
python manage.py runserver
```

## 🔧 환경변수 설정

`.env` 파일에서 다음 변수들을 설정해주세요:

```env
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# OpenAI
OPENAI_API_KEY=your-openai-api-key

# Stripe
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...

# Redis
REDIS_URL=redis://localhost:6379/0
```

## 📚 API 문서

서버 실행 후 다음 주소에서 API 문서를 확인할 수 있습니다:

- **Swagger UI**: http://localhost:8000/api/docs/
- **ReDoc**: http://localhost:8000/api/redoc/
- **Schema**: http://localhost:8000/api/schema/

## 🛣️ API 엔드포인트

### 인증 (Authentication)
- `POST /api/auth/register/` - 회원가입
- `POST /api/auth/login/` - 로그인
- `POST /api/auth/logout/` - 로그아웃
- `GET/PUT /api/auth/profile/` - 프로필 조회/수정

### 학습 (Study)
- `GET /api/study/subjects/` - 과목 목록
- `GET/POST/PUT/DELETE /api/study/settings/` - 학습 설정
- `GET /api/study/summaries/` - 학습 요약 목록
- `POST /api/study/generate-summary/` - 요약 생성
- `GET /api/study/progress/` - 학습 진도

### 퀴즈 (Quiz)
- `GET /api/quiz/quizzes/` - 퀴즈 목록
- `POST /api/quiz/attempt/` - 퀴즈 응답
- `GET /api/quiz/sessions/` - 퀴즈 세션

### 구독 (Subscription)
- `GET /api/subscription/plans/` - 구독 플랜 목록
- `POST /api/subscription/subscribe/` - 구독하기
- `GET /api/subscription/my-subscriptions/` - 내 구독 목록

### 알림 (Notifications)
- `GET /api/notifications/` - 알림 목록
- `POST /api/notifications/device-token/` - 디바이스 토큰 등록

## 📁 프로젝트 구조

```
StudyMate-API/
├── 📁 studymate_api/           # Django 프로젝트 설정
│   ├── settings.py            # 환경설정
│   ├── urls.py               # URL 라우팅
│   └── wsgi.py               # WSGI 설정
├── 📁 accounts/               # 사용자 인증 & 프로필
│   ├── models.py             # User, UserProfile 모델
│   ├── views.py              # 회원가입, 로그인 API
│   ├── serializers.py        # 데이터 직렬화
│   └── urls.py               # 인증 관련 URL
├── 📁 study/                  # 학습 관리 시스템
│   ├── models.py             # Subject, StudySettings, StudySummary 모델
│   ├── services.py           # OpenAI GPT 통합 서비스
│   ├── views.py              # 학습 관련 API
│   └── admin.py              # Django 관리자 설정
├── 📁 quiz/                   # 퀴즈 시스템
│   ├── models.py             # Quiz, QuizAttempt 모델
│   ├── views.py              # 퀴즈 관련 API
│   └── serializers.py        # 퀴즈 데이터 직렬화
├── 📁 subscription/           # 구독 & 결제
│   ├── models.py             # SubscriptionPlan, Payment 모델
│   ├── views.py              # Stripe 결제 API
│   └── services.py           # 결제 처리 로직
├── 📁 notifications/          # 알림 시스템
│   ├── models.py             # Notification, DeviceToken 모델
│   ├── tasks.py              # Celery 백그라운드 작업
│   └── views.py              # 알림 관련 API
├── 📄 requirements.txt        # Python 패키지 의존성
├── 📄 .env.example           # 환경변수 템플릿
├── 📄 docker-compose.yml     # Docker 컨테이너 설정
└── 📄 manage.py              # Django 관리 명령어
```

## 🔌 주요 API 모듈

### **1. Authentication (`/api/auth/`)**
```python
# 사용자 인증 관련 API
POST /api/auth/register/     # 회원가입
POST /api/auth/login/        # 로그인  
POST /api/auth/logout/       # 로그아웃
GET  /api/auth/profile/      # 프로필 조회
PUT  /api/auth/profile/      # 프로필 수정
```

### **2. Study Management (`/api/study/`)**
```python
# 학습 관리 API
GET  /api/study/subjects/           # 과목 목록
POST /api/study/settings/           # 학습 설정 생성
GET  /api/study/settings/           # 내 학습 설정 조회
POST /api/study/generate-summary/   # AI 요약 생성
GET  /api/study/summaries/          # 내 학습 요약 목록
GET  /api/study/progress/           # 학습 진도 조회
```

### **3. Quiz System (`/api/quiz/`)**
```python
# 퀴즈 관련 API  
GET  /api/quiz/quizzes/       # 퀴즈 목록
POST /api/quiz/attempt/       # 퀴즈 응답 제출
GET  /api/quiz/sessions/      # 퀴즈 세션 조회
GET  /api/quiz/results/       # 퀴즈 결과 조회
```

### **4. Subscription (`/api/subscription/`)**
```python
# 구독 및 결제 API
GET  /api/subscription/plans/           # 구독 플랜 목록
POST /api/subscription/subscribe/       # 구독하기
GET  /api/subscription/my-subscriptions/ # 내 구독 목록
POST /api/subscription/webhook/         # Stripe 웹훅
```

### **5. Notifications (`/api/notifications/`)**
```python
# 알림 관련 API
GET  /api/notifications/              # 내 알림 목록
POST /api/notifications/device-token/ # 디바이스 토큰 등록
PUT  /api/notifications/preferences/  # 알림 설정 변경
```

## 🧪 테스트

```bash
python manage.py test
```

## 🚀 배포

배포 관련 설정은 별도 문서에서 확인하세요.

## 📄 라이선스

이 프로젝트는 비공개 프로젝트입니다.

## 🤝 기여

현재는 개인 프로젝트로 진행 중입니다.

## 📞 연락처

프로젝트 관련 문의사항이 있으시면 이슈를 생성해주세요.