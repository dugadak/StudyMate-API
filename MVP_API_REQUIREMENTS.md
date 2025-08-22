# StudyMate MVP API 요구사항

## 📊 유저 플로우 분석 결과

### 제외할 Beta 기능들
- 실험실 Beta
- AI 코치 
- 고급 분석 (프로)
- 리포트 내보내기 (프로)
- 알림 예약 (프로)
- CSV/PNG 공유 링크 (프로)
- 기록 저장 내보내기 (프로)

### MVP에 포함할 핵심 기능

## 🔑 인증 및 계정 관리

### 1. 회원가입/로그인
- `POST /api/auth/register/` - 회원가입
- `POST /api/auth/login/` - 로그인
- `POST /api/auth/logout/` - 로그아웃
- `POST /api/auth/skip/` - 건너뛰기 (게스트 모드)
- `GET /api/auth/profile/` - 프로필 조회
- `PUT /api/auth/profile/` - 프로필 수정
- `PUT /api/auth/preferences/` - 학습 선호 설정 (목표, 과목, 난이도, 톤)

## 📚 학습 관리

### 2. 홈 대시보드
- `GET /api/home/dashboard/` - 대시보드 (연속학습, 진도, 정답률, 시간, 성취도)
- `GET /api/home/stats/` - 통계 개요 (패턴, 추세, 집중시간, 히트맵)

### 3. AI 요약 기능
- `POST /api/study/summary/generate/` - 요약 생성 (텍스트/링크/붙여넣기 입력)
- `GET /api/study/summary/today/` - 오늘의 요약
- `GET /api/study/summary/list/` - 저장된 요약 목록
- `GET /api/study/summary/{id}/` - 요약 상세 보기
- `POST /api/study/summary/{id}/save/` - 요약 저장
- `POST /api/study/summary/{id}/share/` - 요약 공유
- `GET /api/study/daily-limit/` - 일일 무료 한도 확인

## 🎯 퀴즈 시스템

### 4. AI 퀴즈
- `POST /api/quiz/generate/` - AI 기반 퀴즈 생성
- `GET /api/quiz/list/` - 퀴즈 목록
- `GET /api/quiz/{id}/` - 퀴즈 상세
- `POST /api/quiz/{id}/start/` - 퀴즈 시작
- `POST /api/quiz/{id}/answer/` - 답안 제출
- `GET /api/quiz/{id}/result/` - 결과 보기 (랭킹, 오답, 개요)
- `POST /api/quiz/{id}/retry/` - 재도전
- `POST /api/quiz/{id}/save-wrong/` - 오답 노트 저장
- `GET /api/quiz/wrong-answers/` - 오답 노트 목록

### 5. 퀴즈 설정
- `POST /api/quiz/personalize/` - 개인화 설정 (난이도, 길이, 톤)
- `POST /api/quiz/type/` - 유형 선택 (객관식/주관식)

## 👥 협업 학습

### 6. 라이브 그룹 퀴즈
- `GET /api/collab/rooms/` - 룸 리스트
- `POST /api/collab/rooms/create/` - 룸 생성 (제목, 과목, 인원, 비밀번호, 타이머)
- `POST /api/collab/rooms/{id}/join/` - 룸 입장
- `GET /api/collab/rooms/{id}/` - 대기실 (참가자 목록, 준비 완료, 채팅)
- `POST /api/collab/rooms/{id}/start/` - 호스트 시작
- `GET /api/collab/rooms/{id}/live/` - 실시간 순위, 채팅, QnA
- `POST /api/collab/rooms/{id}/answer/` - 라이브 퀴즈 답안 제출

## 💳 구독 및 결제

### 7. 구독 관리
- `GET /api/subscription/plans/` - 구독 플랜 목록
- `POST /api/subscription/upgrade/` - 업그레이드 (구독/크레딧 선택)
- `POST /api/subscription/payment/` - 결제 처리
- `GET /api/subscription/status/` - 구독 상태 확인
- `GET /api/subscription/paywall/` - 페이월 안내

## 🔔 알림 시스템

### 8. 알림 설정 (기본 기능만)
- `POST /api/notifications/permission/` - 알림 권한 동의
- `GET /api/notifications/settings/` - 알림 설정 조회
- `PUT /api/notifications/settings/` - 알림 설정 변경 (09/12/21 고정 시간)
- `POST /api/notifications/snooze/` - 스누즈 (내일 같은 시간)
- `GET /api/notifications/list/` - 알림 목록

## 📊 통계 및 분석 (기본)

### 9. 학습 통계
- `GET /api/stats/overview/` - 전체 통계
- `GET /api/stats/period/` - 기간별 통계 (7일/30일/전체)
- `GET /api/stats/strengths/` - 강약점 자동 파악 (과목×난이도)
- `GET /api/stats/peer-comparison/` - 또래 대비 성과 비교

## 🔧 시스템 기능

### 10. 시스템 알림 (자동)
- 최근 3일 미접속 부드러운 리마인더
- 최근 7일 미접속 복귀 유도
- 알림 스케줄 기본 설정 (09/12/21)

---

## ⚠️ 제거/수정 사항

### 제거할 기능 (Beta)
1. **studymate_api/ab_testing.py** - A/B 테스트 시스템
2. **studymate_api/auto_recovery.py** - 자동 복구 시스템  
3. **studymate_api/distributed_tracing.py** - 분산 추적
4. **studymate_api/zero_trust_security.py** - Zero Trust 보안 (기본 인증만 유지)
5. **studymate_api/advanced_cache.py** - 고급 캐싱 (기본 캐시만 유지)
6. **studymate_api/cqrs.py** - CQRS 패턴 (단순화)
7. **study/realtime_views.py** - 실시간 분석 (협업 학습만 유지)

### 수정할 URL
```python
# studymate_api/urls.py 에서 제거
- path('api/cqrs/', include('studymate_api.cqrs_urls')),
- path('api/ab-testing/', include('studymate_api.urls.ab_testing_urls')),  
- path('api/auto-recovery/', include('studymate_api.urls.auto_recovery_urls')),

# 추가할 URL
+ path('api/home/', include('home.urls')),
+ path('api/collab/', include('collaboration.urls')),
+ path('api/stats/', include('stats.urls')),
```

### 새로 생성할 앱
1. **home** - 홈 대시보드 관리
2. **collaboration** - 협업 학습 (라이브 그룹 퀴즈)
3. **stats** - 통계 및 분석

---

## 📝 구현 우선순위

### Phase 1 (즉시)
1. 인증 시스템 (회원가입/로그인/건너뛰기)
2. 홈 대시보드
3. AI 요약 생성 기능
4. 기본 퀴즈 기능

### Phase 2 (다음)
1. 협업 학습 (라이브 그룹 퀴즈)
2. 구독/결제 시스템
3. 알림 기능
4. 통계 분석

---

## 🔍 주요 변경사항 요약

1. **Beta 기능 제거**: 복잡한 고급 기능들 제거
2. **MVP 집중**: 핵심 학습 기능에 집중
3. **단순화**: CQRS, 분산 추적 등 복잡한 패턴 제거
4. **새 기능 추가**: 협업 학습, 홈 대시보드, 통계
5. **유저 플로우 준수**: SVG 파일의 플로우 정확히 구현