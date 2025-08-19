# StudyMate API Server

> StudyMate 서비스의 백엔드 API 서버

AI 기반 개인화 학습 플랫폼 StudyMate의 서버 사이드 애플리케이션입니다. Django REST Framework를 기반으로 구축되었으며, 실시간 학습 분석, CQRS 패턴, OpenAI GPT를 활용한 개인화 학습 콘텐츠 생성 및 Stripe 결제 시스템을 제공합니다.

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

- 🔐 **인증 시스템**: JWT 기반 인증 및 권한 관리
- 📚 **학습 관리**: 개인화 설정 및 진도 추적
- ⚡ **실시간 분석**: WebSocket 기반 학습 패턴 분석 ✨ **최신!**
- 🏗️ **CQRS 아키텍처**: 명령/조회 분리 패턴 ✨ **최신!**
- 📊 **스트리밍 처리**: 대용량 실시간 데이터 처리 ✨ **최신!**
- 🎯 **개인화 엔진**: AI 기반 학습 스타일 분석 및 추천
- 🤖 **AI 엔진**: 다중 AI 제공자 통합 서비스
- 📝 **퀴즈 엔진**: 문제 생성 및 채점 시스템
- 🔔 **알림 서버**: Celery 기반 스케줄링
- 💳 **결제 처리**: Stripe 웹훅 및 구독 관리
- 🚀 **고급 캐싱**: 태그 기반 캐시 무효화 시스템

## 🛠️ 기술 스택

### **Backend Framework**
- **Django 5.2**: 웹 프레임워크
- **Django REST Framework 3.16**: REST API 개발
- **Django Channels 4.0**: WebSocket 지원 ✨ **최신!**
- **Python 3.10+**: 프로그래밍 언어

### **Database & Cache**
- **PostgreSQL**: 프로덕션 데이터베이스
- **SQLite**: 개발환경 데이터베이스
- **Redis**: 캐싱, 세션 스토어, 채널 레이어 ✨ **업그레이드!**

### **Real-time & Architecture** ✨ **최신 추가!**
- **WebSocket**: 실시간 양방향 통신
- **CQRS Pattern**: 명령/조회 분리 아키텍처
- **Event Sourcing**: 이벤트 기반 데이터 저장
- **Streaming Processing**: 대용량 실시간 데이터 처리

### **External Services**
- **OpenAI GPT-3.5/4**: AI 콘텐츠 생성
- **Anthropic Claude**: AI 모델 통합 ✨ **최신!**
- **Together AI**: 추가 AI 제공자 ✨ **최신!**
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

7. **실시간 분석 시스템 시작** ✨ **최신!**
```bash
python manage.py realtime_analytics_management --start-streaming
```

8. **서버 실행**
```bash
# HTTP/WebSocket 동시 지원 (ASGI 서버 사용)
daphne studymate_api.asgi:application --port 8000

# 또는 개발용 서버 (HTTP만 지원)
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

# 실시간 분석 설정 (선택사항) ✨ 최신!
REALTIME_ANALYSIS_INTERVAL=30
REALTIME_FOCUS_WINDOW=300
REALTIME_MAX_SESSIONS=1000
```

## 📚 API 문서

서버 실행 후 다음 주소에서 API 문서를 확인할 수 있습니다:

- **Swagger UI**: http://localhost:8000/api/docs/
- **ReDoc**: http://localhost:8000/api/redoc/
- **Schema**: http://localhost:8000/api/schema/
- **실시간 대시보드**: http://localhost:8000/templates/realtime_dashboard.html ✨ **최신!**

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

### 실시간 학습 분석 ✨ **최신!**
- `POST /api/study/realtime/learning/start_session/` - 학습 세션 시작
- `POST /api/study/realtime/learning/end_session/` - 세션 종료
- `GET /api/study/realtime/learning/session_status/` - 세션 상태 조회
- `GET /api/study/realtime/learning/active_sessions/` - 활성 세션 목록
- `GET /api/study/realtime/learning/dashboard/` - 실시간 대시보드 데이터

### CQRS 패턴 API ✨ **최신!**
- `POST /api/cqrs/subjects/` - 명령: 과목 생성
- `GET /api/cqrs/subjects/` - 조회: 과목 목록
- `POST /api/cqrs/subjects/{id}/generate_summary/` - AI 요약 생성
- `GET /api/cqrs/study-summaries/` - 요약 목록 조회
- `GET /api/cqrs/study-progress/` - 진도 조회

### WebSocket 엔드포인트 ✨ **최신!**
- `ws://localhost:8000/ws/learning/analytics/` - 실시간 학습 분석
- `ws://localhost:8000/ws/study/room/{room_id}/` - 그룹 스터디룸
- `ws://localhost:8000/ws/system/monitoring/` - 시스템 모니터링 (관리자용)

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