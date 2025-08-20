# 🔌 API Reference

> **개발자를 위한 TimeTree Scheduler API 문서**

## 📋 목차
- [기본 정보](#-기본-정보)
- [인증](#-인증)
- [사용자 관리](#-사용자-관리)  
- [캘린더 API](#-캘린더-api)
- [이벤트 API](#-이벤트-api)
- [채팅 API](#-채팅-api)
- [에러 처리](#-에러-처리)
- [SDK & 예시](#-sdk--예시)

---

## 🌐 기본 정보

### Base URL
```
Production:  https://api.timetree-scheduler.com
Development: http://localhost:8000
```

### 공통 헤더
```http
Content-Type: application/json
Accept: application/json
Authorization: Bearer {access_token}
```

### API 버전
- **현재 버전**: v1
- **호환성**: OAuth 2.0, OpenAPI 3.0

---

## 🔐 인증

### OAuth 2.0 Flow

#### 1. 인증 URL 생성
```http
GET /auth/timetree/login
```

**Response:**
```json
{
  "authorization_url": "https://timetreeapp.com/oauth/authorize?client_id=...",
  "state": "csrf_token_12345",
  "message": "TimeTree 로그인 페이지로 이동하세요."
}
```

#### 2. 콜백 처리 (자동)
```http
GET /auth/timetree/callback?code={code}&state={state}
```

**자동 리다이렉트 URL:**
```
성공: http://localhost:3000/auth/callback?success=true&access_token=...
실패: http://localhost:3000/auth/callback?error=authorization_failed
```

#### 3. 토큰 갱신
```http
POST /auth/refresh
Content-Type: application/json

{
  "refresh_token": "refresh_token_here"
}
```

**Response:**
```json
{
  "access_token": "new_access_token",
  "refresh_token": "new_refresh_token", 
  "token_type": "bearer",
  "expires_in": 1800
}
```

---

## 👤 사용자 관리

### 현재 사용자 정보
```http
GET /auth/me
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "id": "uuid-user-id",
  "email": "user@example.com",
  "name": "홍길동",
  "timetree_user_id": "timetree_123",
  "avatar_url": "https://avatar.url",
  "timezone": "Asia/Seoul",
  "created_at": "2024-01-15T10:30:00Z",
  "last_login_at": "2024-01-15T10:30:00Z"
}
```

### 로그아웃
```http
POST /auth/logout
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "message": "로그아웃이 완료되었습니다.",
  "status": "success"
}
```

### 계정 삭제
```http
DELETE /auth/me
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "message": "계정이 완전히 삭제되었습니다.",
  "status": "success"
}
```

---

## 📅 캘린더 API

### 캘린더 목록 조회
```http
GET /calendars
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "calendars": [
    {
      "id": "uuid-calendar-id",
      "timetree_calendar_id": "timetree_cal_123",
      "name": "가족 캘린더",
      "description": "가족 일정 공유",
      "color": "#FF6B6B",
      "calendar_type": "shared",
      "permission": "read_write",
      "is_active": true,
      "is_default": false,
      "can_write": true,
      "can_admin": false
    }
  ],
  "total_count": 3
}
```

### 특정 캘린더 조회
```http
GET /calendars/{calendar_id}
Authorization: Bearer {access_token}
```

### 캘린더 동기화
```http
POST /calendars/sync
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "message": "캘린더 동기화가 완료되었습니다.",
  "synced_calendars": 3,
  "new_calendars": 1
}
```

---

## 📋 이벤트 API

### 이벤트 목록 조회
```http
GET /events?calendar_id={id}&start_date={date}&end_date={date}
Authorization: Bearer {access_token}
```

**Query Parameters:**
- `calendar_id` (optional): 특정 캘린더 필터
- `start_date` (optional): 시작 날짜 (YYYY-MM-DD)
- `end_date` (optional): 종료 날짜 (YYYY-MM-DD)
- `status` (optional): 이벤트 상태 (draft, confirmed, synced)
- `page` (optional): 페이지 번호 (기본값: 1)
- `limit` (optional): 페이지당 항목 수 (기본값: 20)

**Response:**
```json
{
  "events": [
    {
      "id": "uuid-event-id",
      "title": "팀 회의",
      "description": "",
      "location": "",
      "start_at": "2024-01-16T14:00:00+09:00",
      "end_at": "2024-01-16T15:00:00+09:00",
      "all_day": false,
      "timezone": "Asia/Seoul",
      "category": "schedule",
      "labels": ["업무", "회의"],
      "status": "synced",
      "is_confirmed": true,
      "calendar_id": "uuid-calendar-id",
      "timetree_event_id": "timetree_event_123"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 45,
    "total_pages": 3
  }
}
```

### 이벤트 미리보기 (AI 파싱)
```http
POST /events/preview
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "message": "내일 오후 2시 팀 회의",
  "calendar_id": "uuid-calendar-id",
  "timezone": "Asia/Seoul"
}
```

**Response:**
```json
{
  "parsed_event": {
    "title": "팀 회의",
    "description": "",
    "location": "",
    "start_at": "2024-01-16T14:00:00+09:00",
    "end_at": "2024-01-16T15:00:00+09:00",
    "all_day": false,
    "timezone": "Asia/Seoul",
    "category": "schedule",
    "labels": ["업무", "회의"],
    "confidence": 0.9,
    "parsed_elements": {
      "date_mentions": ["내일"],
      "time_mentions": ["오후 2시"],
      "location_mentions": [],
      "duration_mentions": []
    }
  },
  "conflicts": [],
  "suggestions": [
    "회의실을 예약하시겠습니까?",
    "참석자를 추가하시겠습니까?"
  ]
}
```

### 이벤트 확정 및 등록
```http
POST /events/confirm
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "parsed_event": {
    "title": "팀 회의",
    "start_at": "2024-01-16T14:00:00+09:00",
    "end_at": "2024-01-16T15:00:00+09:00",
    "category": "schedule"
  },
  "calendar_id": "uuid-calendar-id"
}
```

**Response:**
```json
{
  "event": {
    "id": "uuid-event-id",
    "title": "팀 회의",
    "timetree_event_id": "timetree_event_123",
    "status": "synced",
    "timetree_url": "https://timetreeapp.com/calendars/123/events/456"
  },
  "message": "일정이 성공적으로 등록되었습니다."
}
```

### 이벤트 수정
```http
PUT /events/{event_id}
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "title": "수정된 제목",
  "start_at": "2024-01-16T15:00:00+09:00",
  "end_at": "2024-01-16T16:00:00+09:00"
}
```

### 이벤트 삭제
```http
DELETE /events/{event_id}
Authorization: Bearer {access_token}
```

---

## 💬 채팅 API

### 메시지 전송 (AI 파싱)
```http
POST /chat/message
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "message": "내일 오후 2시 치과 예약",
  "context": {
    "calendar_id": "uuid-calendar-id",
    "timezone": "Asia/Seoul",
    "user_preferences": {}
  }
}
```

**Response:**
```json
{
  "response_type": "event_parsed",
  "parsed_event": {
    "title": "치과 예약",
    "start_at": "2024-01-16T14:00:00+09:00",
    "end_at": "2024-01-16T15:00:00+09:00",
    "confidence": 0.95
  },
  "message": "치과 예약 일정을 분석했습니다. 등록하시겠습니까?",
  "suggestions": [
    "등록하기",
    "시간 수정",
    "취소"
  ],
  "session_id": "session_123"
}
```

### 채팅 히스토리
```http
GET /chat/history?limit=20&offset=0
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "messages": [
    {
      "id": "msg_123",
      "role": "user",
      "content": "내일 오후 2시 치과 예약",
      "timestamp": "2024-01-15T10:30:00Z"
    },
    {
      "id": "msg_124", 
      "role": "assistant",
      "content": "치과 예약 일정을 분석했습니다.",
      "parsed_data": { "title": "치과 예약" },
      "timestamp": "2024-01-15T10:30:05Z"
    }
  ],
  "total_count": 45
}
```

---

## ❌ 에러 처리

### 에러 응답 형식
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "입력 데이터가 올바르지 않습니다.",
    "details": {
      "field": "start_at",
      "issue": "날짜 형식이 잘못되었습니다."
    },
    "timestamp": "2024-01-15T10:30:00Z",
    "request_id": "req_123"
  }
}
```

### 에러 코드

| HTTP Code | Error Code | 설명 |
|-----------|-----------|------|
| 400 | `VALIDATION_ERROR` | 요청 데이터 검증 실패 |
| 401 | `UNAUTHORIZED` | 인증되지 않은 요청 |
| 403 | `FORBIDDEN` | 권한 없음 |
| 404 | `NOT_FOUND` | 리소스를 찾을 수 없음 |
| 409 | `CONFLICT` | 리소스 충돌 (중복 이벤트 등) |
| 429 | `RATE_LIMIT_EXCEEDED` | 요청 한도 초과 |
| 500 | `INTERNAL_ERROR` | 서버 내부 오류 |
| 502 | `EXTERNAL_API_ERROR` | 외부 API (TimeTree/Claude) 오류 |
| 503 | `SERVICE_UNAVAILABLE` | 서비스 일시적 불가 |

### TimeTree API 관련 에러

| Error Code | 설명 | 해결 방법 |
|-----------|------|----------|
| `TIMETREE_RATE_LIMIT` | TimeTree API 요청 한도 초과 | 잠시 후 재시도 |
| `TIMETREE_PERMISSION_DENIED` | 캘린더 권한 없음 | 캘린더 권한 확인 |
| `TIMETREE_CALENDAR_NOT_FOUND` | 캘린더를 찾을 수 없음 | 캘린더 ID 확인 |
| `TIMETREE_TOKEN_EXPIRED` | 토큰 만료 | 토큰 갱신 필요 |

### AI 파싱 관련 에러

| Error Code | 설명 | 해결 방법 |
|-----------|------|----------|
| `AI_PARSE_FAILED` | AI 파싱 실패 | 더 명확한 표현으로 재시도 |
| `AI_LOW_CONFIDENCE` | 파싱 신뢰도 낮음 | 결과 검토 후 수정 |
| `AI_TIMEOUT` | AI 응답 시간 초과 | 잠시 후 재시도 |
| `AI_QUOTA_EXCEEDED` | AI API 할당량 초과 | 관리자에게 문의 |

---

## 🛠️ SDK & 예시

### JavaScript/TypeScript SDK

#### 설치
```bash
npm install @timetree-scheduler/sdk
```

#### 기본 사용법
```typescript
import { TimeTreeScheduler } from '@timetree-scheduler/sdk';

const client = new TimeTreeScheduler({
  apiUrl: 'https://api.timetree-scheduler.com',
  accessToken: 'your_access_token'
});

// 자연어로 이벤트 생성
const result = await client.chat.parseMessage({
  message: '내일 오후 2시 팀 회의',
  calendarId: 'calendar-123'
});

// 이벤트 확정
if (result.parsed_event) {
  const event = await client.events.confirm({
    parsedEvent: result.parsed_event,
    calendarId: 'calendar-123'
  });
  console.log('등록된 이벤트:', event);
}
```

### Python SDK

#### 설치
```bash
pip install timetree-scheduler-sdk
```

#### 기본 사용법
```python
from timetree_scheduler import TimeTreeScheduler

client = TimeTreeScheduler(
    api_url='https://api.timetree-scheduler.com',
    access_token='your_access_token'
)

# 자연어로 이벤트 생성
result = client.chat.parse_message(
    message='내일 오후 2시 팀 회의',
    calendar_id='calendar-123'
)

# 이벤트 확정
if result.parsed_event:
    event = client.events.confirm(
        parsed_event=result.parsed_event,
        calendar_id='calendar-123'
    )
    print(f"등록된 이벤트: {event}")
```

### cURL 예시

#### 이벤트 생성 전체 플로우
```bash
# 1. 자연어 파싱
curl -X POST https://api.timetree-scheduler.com/chat/message \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "내일 오후 2시 팀 회의",
    "context": {
      "calendar_id": "calendar-123",
      "timezone": "Asia/Seoul"
    }
  }'

# 2. 이벤트 확정
curl -X POST https://api.timetree-scheduler.com/events/confirm \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "parsed_event": {
      "title": "팀 회의",
      "start_at": "2024-01-16T14:00:00+09:00",
      "end_at": "2024-01-16T15:00:00+09:00",
      "category": "schedule"
    },
    "calendar_id": "calendar-123"
  }'
```

---

## 🔧 개발 도구

### Postman Collection
```
Import URL: https://api.timetree-scheduler.com/postman/collection.json
```

### OpenAPI Spec
```
Swagger UI: https://api.timetree-scheduler.com/docs
OpenAPI JSON: https://api.timetree-scheduler.com/openapi.json
```

### 테스트 환경
```
Test API: https://test-api.timetree-scheduler.com
Test Account: test@timetree-scheduler.com / test123!
```

---

## 📊 레이트 리밋

| 엔드포인트 | 제한 | 기간 |
|-----------|------|------|
| `/chat/message` | 60 requests | 1분 |
| `/events/confirm` | 30 requests | 1분 |
| `/auth/*` | 10 requests | 1분 |
| 기타 API | 100 requests | 1분 |

### 레이트 리밋 헤더
```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 59
X-RateLimit-Reset: 1642771200
```

---

*🚀 더 자세한 정보는 [개발자 포털](https://developers.timetree-scheduler.com)에서 확인하세요!*