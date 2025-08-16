# StudyMate API

AI 기반 공부 보조 서비스 백엔드 API

## 🎯 프로젝트 개요

StudyMate는 사용자의 학습 목표와 수준에 맞춰 개인화된 학습 요약과 퀴즈를 제공하는 AI 기반 공부 보조 서비스입니다.

### 주요 기능

- 🔐 **사용자 인증**: 이메일 기반 회원가입/로그인
- 📚 **개인화 학습**: 사용자별 학습 설정 및 진도 관리
- 🤖 **AI 요약 생성**: OpenAI GPT를 활용한 맞춤형 학습 요약
- 📝 **퀴즈 시스템**: 객관식/주관식 문제 및 해설 제공
- 🔔 **알림 시스템**: 학습 스케줄 알림 및 푸시 알림
- 💳 **구독 관리**: Stripe 기반 결제 및 구독 시스템

## 🏗️ 기술 스택

- **Backend**: Django 5.2, Django REST Framework
- **Database**: SQLite (개발), PostgreSQL (프로덕션)
- **Authentication**: Django Token Authentication
- **AI**: OpenAI GPT-3.5/4
- **Payment**: Stripe
- **Task Queue**: Celery + Redis
- **Documentation**: drf-spectacular (Swagger)

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

## 💰 구독 플랜

### 무료 플랜
- 하루 3번 요약 정보 제공 (9시, 12시, 21시 고정)
- 기본 퀴즈 기능

### 유료 플랜
- **퀴즈 10회권**: 4,900원
- **퀴즈 100회권**: 44,900원
- **하루 5번 요약**: 9,900원/월
- **하루 10번 요약**: 16,900원/월
- **시간 변경권 5회**: 9,900원
- **시간 변경권 10회**: 16,900원
- **프로플랜**: 25,900원/월 (모든 기능 포함)

## 🏢 프로젝트 구조

```
StudyMate-API/
├── studymate_api/          # 프로젝트 설정
├── accounts/               # 사용자 인증
├── study/                  # 학습 관리
├── quiz/                   # 퀴즈 시스템
├── subscription/           # 구독 관리
├── notifications/          # 알림 시스템
├── requirements.txt        # 패키지 목록
├── .env.example           # 환경변수 예시
└── README.md              # 프로젝트 문서
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