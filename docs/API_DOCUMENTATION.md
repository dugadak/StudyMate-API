# StudyMate API 문서

## 🎯 개요

StudyMate API는 AI 기반 학습 플랫폼을 위한 RESTful API입니다. 사용자 관리, 학습 콘텐츠, 퀴즈, 구독 관리 등의 기능을 제공합니다.

## 🔗 기본 정보

- **Base URL**: `https://api.studymate.com/api/v1/`
- **인증 방식**: JWT (JSON Web Token)
- **응답 형식**: JSON
- **API 버전**: v1

## 🔐 인증

### JWT 토큰 기반 인증

모든 보호된 엔드포인트는 Authorization 헤더에 Bearer 토큰이 필요합니다.

```http
Authorization: Bearer <your-jwt-token>
```

### 토큰 획득

```http
POST /api/v1/auth/login/
Content-Type: application/json

{
    "email": "user@example.com",
    "password": "yourpassword"
}
```

**응답**:
```json
{
    "success": true,
    "data": {
        "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
        "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
        "user": {
            "id": 1,
            "email": "user@example.com",
            "first_name": "홍",
            "last_name": "길동"
        }
    }
}
```

### 토큰 갱신

```http
POST /api/v1/auth/token/refresh/
Content-Type: application/json

{
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

## 📚 주요 엔드포인트

### 사용자 관리

#### 회원가입
```http
POST /api/v1/auth/register/
Content-Type: application/json

{
    "email": "newuser@example.com",
    "password": "strongpassword123",
    "password2": "strongpassword123",
    "first_name": "김",
    "last_name": "철수",
    "marketing_consent": true
}
```

#### 사용자 프로필 조회
```http
GET /api/v1/accounts/profile/
Authorization: Bearer <token>
```

**응답**:
```json
{
    "success": true,
    "data": {
        "id": 1,
        "email": "user@example.com",
        "profile": {
            "bio": "AI 개발자입니다",
            "learning_streak": 15,
            "total_study_time": 7200,
            "learning_style": "visual"
        },
        "subscription": {
            "plan": "premium",
            "status": "active",
            "expires_at": "2024-12-31T23:59:59Z"
        }
    }
}
```

#### 프로필 업데이트
```http
PATCH /api/v1/accounts/profile/
Authorization: Bearer <token>
Content-Type: application/json

{
    "bio": "업데이트된 자기소개",
    "learning_goals": ["Python 마스터", "AI 엔지니어 되기"],
    "preferred_study_time": "morning"
}
```

### 학습 관리

#### 학습 세션 생성
```http
POST /api/v1/study/sessions/
Authorization: Bearer <token>
Content-Type: application/json

{
    "subject_id": 1,
    "title": "Python 기초 학습",
    "content": "변수와 데이터 타입에 대해 학습",
    "target_duration": 3600,
    "difficulty_level": "beginner"
}
```

**응답**:
```json
{
    "success": true,
    "data": {
        "id": 123,
        "title": "Python 기초 학습",
        "status": "in_progress",
        "created_at": "2024-08-19T10:30:00Z",
        "ai_summary": "이번 세션에서는 Python의 기본 변수 타입과 사용법을 다룹니다.",
        "estimated_completion": "2024-08-19T11:30:00Z"
    }
}
```

#### 학습 세션 목록 조회
```http
GET /api/v1/study/sessions/?page=1&page_size=20&status=completed
Authorization: Bearer <token>
```

**쿼리 매개변수**:
- `page`: 페이지 번호 (기본값: 1)
- `page_size`: 페이지 크기 (기본값: 20, 최대: 100)
- `status`: 세션 상태 (`in_progress`, `completed`, `paused`)
- `subject`: 과목 ID로 필터링
- `date_from`: 시작 날짜 (YYYY-MM-DD)
- `date_to`: 종료 날짜 (YYYY-MM-DD)
- `search`: 제목 검색

#### AI 요약 생성
```http
POST /api/v1/study/sessions/123/generate-summary/
Authorization: Bearer <token>
Content-Type: application/json

{
    "content": "오늘 학습한 Python 변수와 데이터 타입 내용...",
    "include_quiz": true,
    "summary_type": "detailed"
}
```

### 퀴즈 시스템

#### 퀴즈 생성
```http
POST /api/v1/quiz/quizzes/
Authorization: Bearer <token>
Content-Type: application/json

{
    "title": "Python 기초 퀴즈",
    "description": "변수와 데이터 타입에 대한 퀴즈",
    "subject_id": 1,
    "difficulty": "beginner",
    "questions": [
        {
            "question": "Python에서 문자열을 나타내는 타입은?",
            "type": "multiple_choice",
            "choices": [
                {"text": "str", "is_correct": true},
                {"text": "string", "is_correct": false},
                {"text": "text", "is_correct": false},
                {"text": "char", "is_correct": false}
            ],
            "explanation": "Python에서 문자열은 str 타입으로 표현됩니다."
        }
    ]
}
```

#### 퀴즈 풀이 시작
```http
POST /api/v1/quiz/attempts/
Authorization: Bearer <token>
Content-Type: application/json

{
    "quiz_id": 456
}
```

#### 답안 제출
```http
POST /api/v1/quiz/attempts/789/submit-answer/
Authorization: Bearer <token>
Content-Type: application/json

{
    "question_id": 101,
    "selected_choices": [1],
    "answer_text": null,
    "time_spent": 30
}
```

### 구독 관리

#### 구독 플랜 목록
```http
GET /api/v1/subscription/plans/
```

**응답**:
```json
{
    "success": true,
    "data": [
        {
            "id": 1,
            "name": "Basic",
            "price": 9900,
            "currency": "KRW",
            "interval": "monthly",
            "features": [
                "월 100개 AI 요약",
                "기본 퀴즈 생성",
                "학습 진도 추적"
            ]
        },
        {
            "id": 2,
            "name": "Premium",
            "price": 19900,
            "currency": "KRW",
            "interval": "monthly",
            "features": [
                "무제한 AI 요약",
                "고급 퀴즈 생성",
                "맞춤형 학습 경로",
                "실시간 분석",
                "우선 고객 지원"
            ]
        }
    ]
}
```

#### 구독 신청
```http
POST /api/v1/subscription/subscribe/
Authorization: Bearer <token>
Content-Type: application/json

{
    "plan_id": 2,
    "payment_method": "stripe",
    "payment_token": "pm_1234567890"
}
```

### 알림 시스템

#### 알림 목록 조회
```http
GET /api/v1/notifications/?unread_only=true
Authorization: Bearer <token>
```

#### 알림 읽음 처리
```http
PATCH /api/v1/notifications/123/
Authorization: Bearer <token>
Content-Type: application/json

{
    "is_read": true
}
```

### 개인화 및 추천

#### 맞춤형 학습 추천
```http
GET /api/v1/personalization/recommendations/
Authorization: Bearer <token>
```

**응답**:
```json
{
    "success": true,
    "data": {
        "recommended_subjects": [
            {
                "id": 1,
                "name": "Python 고급",
                "reason": "현재 Python 기초를 완료하신 상태입니다",
                "confidence": 0.85
            }
        ],
        "study_schedule": {
            "optimal_time": "09:00-11:00",
            "recommended_duration": 90,
            "break_intervals": [30, 60]
        },
        "next_review_topics": [
            {
                "topic": "변수와 데이터 타입",
                "due_date": "2024-08-20T09:00:00Z",
                "confidence_level": 0.7
            }
        ]
    }
}
```

## 📊 응답 형식

### 성공 응답
```json
{
    "success": true,
    "data": {
        // 실제 데이터
    },
    "message": "작업이 성공적으로 완료되었습니다.",
    "meta": {
        "pagination": {
            "page": 1,
            "page_size": 20,
            "total_pages": 5,
            "total_count": 89
        },
        "timestamp": "2024-08-19T10:30:00Z"
    }
}
```

### 에러 응답
```json
{
    "success": false,
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "입력 데이터가 유효하지 않습니다.",
        "details": {
            "email": ["유효한 이메일 주소를 입력하세요."],
            "password": ["비밀번호는 최소 8자 이상이어야 합니다."]
        }
    },
    "meta": {
        "timestamp": "2024-08-19T10:30:00Z",
        "request_id": "req_12345"
    }
}
```

## 🔢 HTTP 상태 코드

| 코드 | 의미 | 설명 |
|------|------|------|
| 200 | OK | 요청 성공 |
| 201 | Created | 리소스 생성 성공 |
| 400 | Bad Request | 잘못된 요청 |
| 401 | Unauthorized | 인증 필요 |
| 403 | Forbidden | 권한 없음 |
| 404 | Not Found | 리소스 없음 |
| 422 | Unprocessable Entity | 유효성 검사 실패 |
| 429 | Too Many Requests | 요청 한도 초과 |
| 500 | Internal Server Error | 서버 오류 |

## 📝 에러 코드

| 코드 | 설명 |
|------|------|
| `VALIDATION_ERROR` | 입력 데이터 유효성 검사 실패 |
| `AUTHENTICATION_FAILED` | 인증 실패 |
| `PERMISSION_DENIED` | 권한 없음 |
| `NOT_FOUND` | 리소스를 찾을 수 없음 |
| `RATE_LIMIT_EXCEEDED` | 요청 한도 초과 |
| `PAYMENT_FAILED` | 결제 실패 |
| `SUBSCRIPTION_REQUIRED` | 구독 필요 |
| `AI_SERVICE_ERROR` | AI 서비스 오류 |

## 🚦 요청 제한

### 기본 제한
- **인증된 사용자**: 1000 req/hour
- **익명 사용자**: 100 req/hour
- **AI 요약 생성**: 50 req/hour (Basic), 무제한 (Premium)
- **파일 업로드**: 10 MB/request

### 헤더 정보
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1692435600
```

## 📱 WebSocket API

### 실시간 학습 분석
```javascript
// WebSocket 연결
const ws = new WebSocket('wss://api.studymate.com/ws/study/analytics/');

// 인증
ws.send(JSON.stringify({
    type: 'authenticate',
    token: 'your-jwt-token'
}));

// 학습 진도 실시간 업데이트 구독
ws.send(JSON.stringify({
    type: 'subscribe',
    channel: 'study_progress'
}));

// 메시지 수신
ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('실시간 업데이트:', data);
};
```

## 🧪 테스트 및 개발

### API 테스트 도구

**cURL 예시**:
```bash
# 로그인
curl -X POST https://api.studymate.com/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "testpass123"}'

# 인증된 요청
curl -X GET https://api.studymate.com/api/v1/study/sessions/ \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
```

**Postman Collection**: [StudyMate API Collection](https://documenter.getpostman.com/view/studymate-api)

### 샌드박스 환경
- **URL**: `https://sandbox-api.studymate.com/api/v1/`
- **테스트 카드**: `4242424242424242` (Stripe 테스트)
- **제한사항**: 실제 결제 없음, 이메일 발송 없음

## 📖 추가 문서

- [개발 가이드](./DEVELOPMENT_GUIDE.md)
- [CI/CD 파이프라인](./CI_CD_PIPELINE.md)
- [보안 정책](./SECURITY.md)
- [변경 로그](./CHANGELOG.md)

## 🆘 지원

### 기술 지원
- **이메일**: dev@studymate.com
- **Discord**: [StudyMate 개발자 커뮤니티](https://discord.gg/studymate)
- **이슈 트래커**: [GitHub Issues](https://github.com/StudyMate-ComPany/StudyMate-API/issues)

### SLA (Service Level Agreement)
- **가용성**: 99.9%
- **응답 시간**: < 200ms (평균)
- **지원 응답**: 24시간 이내

---

**마지막 업데이트**: 2025년 8월 19일  
**API 버전**: v1.0.0  
**문서 버전**: 2.0.0