# TimeTree Scheduler - 자연어 일정 자동 등록

자연어로 입력한 일정을 ChatGPT AI가 파싱하여 TimeTree 공유 캘린더에 자동으로 등록하는 서비스입니다.

## 아키텍처 다이어그램

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web UI        │    │   FastAPI        │    │   ChatGPT AI    │
│   (Next.js)     │    │   Backend        │    │   (OpenAI)      │
│                 │    │                  │    │                 │
│  ┌─────────────┐│    │ ┌──────────────┐ │    │ ┌─────────────┐ │
│  │ Chat Input  ││◄──►│ │ Chat Router  │ │◄──►│ │ NLU Parser  │ │
│  │             ││    │ │              │ │    │ │             │ │
│  │ Event Card  ││    │ │ Event Router │ │    │ │ JSON Output │ │
│  └─────────────┘│    │ └──────────────┘ │    │ └─────────────┘ │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌──────────────────┐             │
         │              │   PostgreSQL     │             │
         │              │                  │             │
         │              │ ┌──────────────┐ │             │
         └──────────────┼►│ Users        │ │             │
                        │ │ Calendars    │ │             │
                        │ │ Events       │ │◄────────────┘
                        │ │ Tokens       │ │
                        │ └──────────────┘ │
                        └──────────────────┘
                                 │
                        ┌──────────────────┐
                        │   TimeTree API   │
                        │                  │
                        │ ┌──────────────┐ │
                        │ │ OAuth 2.0    │ │
                        │ │ Calendars    │ │
                        │ │ Events CRUD  │ │
                        │ └──────────────┘ │
                        └──────────────────┘
```

## 시퀀스 다이어그램

```
User    Web UI    FastAPI    ChatGPT   TimeTree    PostgreSQL
 │        │          │         │          │            │
 │ "내일 오후 2시 회의" │         │          │            │
 ├───────►│          │         │          │            │
 │        │ POST /chat/message  │          │            │
 │        ├─────────►│         │          │            │
 │        │          │ Parse NL input     │            │
 │        │          ├────────►│          │            │
 │        │          │ JSON event         │            │
 │        │          │◄────────┤          │            │
 │        │          │ Validate & Store   │            │
 │        │          ├─────────────────────────────────►│
 │        │          │         │          │     OK     │
 │        │          │◄─────────────────────────────────┤
 │        │ Event Preview       │          │            │
 │        │◄─────────┤         │          │            │
 │ Review & Confirm  │         │          │            │
 ├───────►│          │         │          │            │
 │        │ POST /events/confirm│          │            │
 │        ├─────────►│         │          │            │
 │        │          │ Create Event       │            │
 │        │          ├──────────────────►│            │
 │        │          │        │    201 Created         │
 │        │          │◄────────────────────│            │
 │        │          │ Update DB          │            │
 │        │          ├─────────────────────────────────►│
 │        │ Success Response    │          │            │
 │        │◄─────────┤         │          │            │
 │◄───────┤          │         │          │            │
```

## 주요 기능

- 🗣️ **자연어 입력**: "내일 오후 2시 팀 회의", "다음주 화요일 종일 휴가" 등
- 🤖 **AI 파싱**: ChatGPT가 날짜/시간/제목/설명을 정확히 추출
- 📅 **TimeTree 연동**: OAuth 인증 및 공유 캘린더 자동 등록
- 🔄 **실시간 미리보기**: 등록 전 일정 내용 확인 및 수정
- 🌏 **한국 시간대**: Asia/Seoul 기준 자동 처리
- 🔒 **보안**: JWT 인증, OAuth 2.0, 토큰 암호화

## 기술 스택

### Frontend
- **Next.js 14** (App Router) + **React 18** + **TypeScript**
- **Tailwind CSS** + **shadcn/ui** (모던 UI 컴포넌트)
- **실시간 채팅 UI** (WebSocket 옵션)

### Backend
- **FastAPI** (Python 3.11+) + **Pydantic v2**
- **PostgreSQL** + **SQLAlchemy 2.x** + **Alembic**
- **OpenAI ChatGPT API** (JSON 전용 프롬프트)
- **TimeTree API** (OAuth 2.0 + Personal Access Token)

### Infrastructure
- **Docker** + **Docker Compose** (로컬/스테이징)
- **Terraform** (AWS ECS/RDS 프로덕션 배포)
- **GitHub Actions** (CI/CD)
- **OpenTelemetry** + **Sentry** (관측성)

## 빠른 시작

### 사전 요구사항

1. **TimeTree 앱 등록**
   - [TimeTree Developer Console](https://timetree.com/developers)에서 앱 생성
   - Redirect URI: `http://localhost:8000/auth/timetree/callback`
   - Client ID, Client Secret 발급

2. **OpenAI API 키**
   - [OpenAI Platform](https://platform.openai.com/)에서 API 키 발급

### 로컬 실행

```bash
# 1. 저장소 클론
git clone https://github.com/your-username/timetree-scheduler.git
cd timetree-scheduler

# 2. 환경 변수 설정
cp .env.example .env
# .env 파일에서 API 키들 설정

# 3. 전체 서비스 실행
make up

# 또는 개별 실행
make setup    # 의존성 설치
make migrate  # DB 마이그레이션
make dev      # 개발 서버 실행
```

브라우저에서 http://localhost:3000 접속

### 사용법

1. **TimeTree 연동**: "로그인" → TimeTree OAuth 인증
2. **캘린더 선택**: 등록할 공유 캘린더 선택
3. **일정 입력**: "내일 오후 3시 치과 예약" 등 자연어로 입력
4. **미리보기 확인**: AI가 파싱한 결과 검토
5. **등록 완료**: "등록" 버튼으로 TimeTree에 이벤트 생성

### 자연어 예시

```
✅ 지원되는 표현:
- "내일 오후 2시 회의"
- "다음주 화요일 종일 연차"
- "12월 25일 오전 10시 크리스마스 파티"
- "매주 월요일 오전 9시 주간회의" (반복 일정)
- "오늘 저녁 7시 홍대에서 저녁식사"

✅ 자동 처리:
- 시간 미지정 → 오전 10:00 기본값
- 종료시간 미지정 → 1시간 후 자동 설정
- "종일" → 00:00~23:59:59
- 상대적 날짜 ("내일", "다음주") → 절대 날짜 변환
```

## API 문서

개발 서버 실행 후 http://localhost:8000/docs 에서 Swagger UI 확인

주요 엔드포인트:
- `POST /chat/message` - 자연어 일정 파싱
- `POST /events/preview` - 이벤트 미리보기
- `POST /events/confirm` - TimeTree 등록
- `GET /me/calendars` - 연동된 캘린더 목록
- `GET /auth/timetree/login` - OAuth 로그인

## 배포

### Docker Compose (권장)

```bash
# 프로덕션 빌드
docker-compose -f docker-compose.prod.yml up -d

# 헬스체크
curl http://localhost:8000/health
```

### AWS (Terraform)

```bash
cd infra/terraform
terraform init
terraform plan
terraform apply

# ECS 서비스 URL 확인
terraform output app_url
```

### 환경 변수

```bash
# 필수
TIMETREE_CLIENT_ID=your_client_id
TIMETREE_CLIENT_SECRET=your_client_secret
OPENAI_API_KEY=your_openai_key
DATABASE_URL=postgresql://user:pass@localhost/db

# 옵션
ENVIRONMENT=production
LOG_LEVEL=INFO
SENTRY_DSN=https://...
```

## 개발

### 백엔드 개발

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 프론트엔드 개발

```bash
cd frontend
npm install
npm run dev
```

### 테스트

```bash
# 백엔드 테스트
make test-backend

# 프론트엔드 테스트  
make test-frontend

# E2E 테스트
make test-e2e
```

### 코드 품질

```bash
# 린팅 & 포맷팅
make lint
make format

# 타입 체크
make typecheck
```

## 아키텍처 세부사항

### 중복 방지 (Idempotency)
- `user_id + calendar_id + title + start_at` 해시로 중복 이벤트 방지
- 24시간 내 동일 이벤트 생성 시 기존 이벤트 반환

### AI 프롬프트 전략
- 단일 프롬프트로 JSON 스키마 강제 출력
- Pydantic 검증 실패 시 자동 재시도 (최대 3회)
- 한국어 시간 표현 특화 ("오후", "저녁", "새벽" 등)

### 에러 처리
- TimeTree API 레이트리밋 자동 백오프
- OpenAI API 장애 시 폴백 파서 (정규식 기반)
- 네트워크 장애 시 지수 백오프 재시도

### 보안
- JWT 토큰 + 리프레시 토큰
- TimeTree 액세스 토큰 AES 암호화 저장
- CORS, CSP, HSTS 헤더 설정
- API 레이트리밋 (유저별/IP별)

## 라이선스

MIT License - 자세한 내용은 [LICENSE](LICENSE) 파일 참조

## 기여

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 지원

- 📧 이메일: support@timetree-scheduler.com
- 🐛 버그 리포트: [GitHub Issues](https://github.com/your-username/timetree-scheduler/issues)
- 💬 커뮤니티: [Discord](https://discord.gg/timetree-scheduler)

---

**Made with ❤️ for seamless calendar management**