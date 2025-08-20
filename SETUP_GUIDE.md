# 🚀 TimeTree Event Creator 설치 및 실행 가이드

> 한국어 자연어를 TimeTree 캘린더 일정으로 자동 변환하는 시스템

## 📋 목차
1. [사전 요구사항](#사전-요구사항)
2. [API 키 발급받기](#api-키-발급받기)
3. [로컬 개발 환경 설정](#로컬-개발-환경-설정)
4. [Docker로 실행하기](#docker로-실행하기)
5. [API 테스트하기](#api-테스트하기)
6. [프로덕션 배포 (Ansible)](#프로덕션-배포-ansible)
7. [트러블슈팅](#트러블슈팅)

---

## 🛠 사전 요구사항

다음 프로그램들이 설치되어 있어야 합니다:

### 필수 설치
```bash
# 1. Docker & Docker Compose 설치 확인
docker --version          # Docker version 20.10+ 필요
docker-compose --version  # Docker Compose version 2.0+ 필요

# 2. Git 설치 확인
git --version

# 3. 텍스트 에디터 (VS Code 권장)
code --version
```

### 설치가 필요한 경우

#### macOS (Homebrew 사용)
```bash
# Homebrew 설치
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Docker Desktop 설치
brew install --cask docker

# Git 설치
brew install git
```

#### Ubuntu/Debian
```bash
# Docker 설치
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Docker Compose 설치
sudo apt-get update
sudo apt-get install docker-compose-plugin

# Git 설치
sudo apt-get install git
```

#### Windows
1. [Docker Desktop for Windows](https://docs.docker.com/desktop/windows/install/) 다운로드 및 설치
2. [Git for Windows](https://git-scm.com/download/win) 다운로드 및 설치

---

## 🔑 API 키 발급받기

### 1. OpenAI API 키 발급 (필수)

**OpenAI ChatGPT API를 사용하므로 반드시 필요합니다.**

1. https://platform.openai.com/ 접속
2. 계정 생성 또는 로그인
3. 우측 상단 프로필 → "View API keys" 클릭
4. "+ Create new secret key" 클릭
5. 키 이름 입력 (예: "TimeTree Creator")
6. 생성된 키 복사 (sk-로 시작하는 키)

**⚠️ 중요: 키는 한 번만 표시되므로 안전한 곳에 저장하세요!**

### 2. TimeTree OAuth 앱 등록

1. https://timetreeapp.com/developers 접속
2. 개발자 계정 생성
3. "새 앱 등록" 클릭
4. 앱 정보 입력:
   - 앱 이름: `TimeTree Event Creator`
   - 리디렉션 URI: `http://localhost:8000/api/v1/auth/timetree/callback`
5. Client ID와 Client Secret 복사

### 3. Stripe 계정 (선택사항 - 결제 기능용)

1. https://stripe.com 접속
2. 계정 생성
3. 대시보드 → "개발자" → "API 키" 에서 테스트 키 복사

---

## 💻 로컬 개발 환경 설정

### 1. 프로젝트 클론

```bash
# 프로젝트 클론
git clone <this-repository-url>
cd StudyMate-API

# 또는 직접 다운로드한 경우
cd StudyMate-API
```

### 2. 환경변수 설정

```bash
# 환경변수 파일 생성
cp .env.example .env

# 텍스트 에디터로 .env 파일 편집
nano .env
# 또는
code .env
```

**.env 파일 설정 예시:**
```bash
# 기본 설정
DEBUG=true
ENVIRONMENT=development

# OpenAI API 키 (필수!)
OPENAI_API_KEY=sk-proj-your-actual-openai-key-here

# TimeTree OAuth (필수!)
TIMETREE_CLIENT_ID=your-timetree-client-id
TIMETREE_CLIENT_SECRET=your-timetree-client-secret

# JWT 시크릿 (32자 이상)
JWT_SECRET_KEY=your-super-secret-jwt-key-minimum-32-characters-long

# 선택사항
STRIPE_PUBLISHABLE_KEY=pk_test_your-stripe-key
STRIPE_SECRET_KEY=sk_test_your-stripe-secret
```

### 3. 로그 디렉토리 생성

```bash
# 로그 디렉토리 생성
mkdir -p logs
```

---

## 🐳 Docker로 실행하기

### 1. Docker Compose로 한 번에 실행

```bash
# 모든 서비스 시작 (첫 실행시 이미지 빌드됨)
docker-compose up -d

# 실행 상태 확인
docker-compose ps
```

**실행되는 서비스들:**
- `postgres`: PostgreSQL 데이터베이스 (포트 5432)
- `redis`: Redis 캐시 (포트 6379)
- `backend`: FastAPI 백엔드 서버 (포트 8000)
- `pgadmin`: 데이터베이스 관리 도구 (포트 5050)

### 2. 서비스 상태 확인

```bash
# 모든 컨테이너 상태 확인
docker-compose ps

# 백엔드 로그 확인
docker-compose logs -f backend

# 데이터베이스 로그 확인
docker-compose logs -f postgres
```

### 3. 데이터베이스 초기 설정

```bash
# 백엔드 컨테이너 접속
docker-compose exec backend bash

# 데이터베이스 마이그레이션 실행
alembic upgrade head

# 슈퍼유저 생성 (선택사항)
python scripts/create_superuser.py
```

---

## 🧪 API 테스트하기

### 1. 헬스 체크

**브라우저에서 접속:**
```
http://localhost:8000/api/health/
```

**cURL로 테스트:**
```bash
curl http://localhost:8000/api/health/
```

**예상 응답:**
```json
{
  "status": "healthy",
  "timestamp": "2024-08-19T12:00:00Z",
  "services": {
    "database": "connected",
    "redis": "connected",
    "openai": "connected"
  }
}
```

### 2. API 문서 확인

**Swagger UI 접속:**
```
http://localhost:8000/docs
```

### 3. 실제 자연어 파싱 테스트

**1) 사용자 등록:**
```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "testpassword123",
    "full_name": "테스트 사용자"
  }'
```

**2) 로그인:**
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test@example.com&password=testpassword123"
```

**3) 자연어 파싱 테스트:**
```bash
# 로그인에서 받은 토큰 사용
TOKEN="your-access-token-here"

curl -X POST "http://localhost:8000/api/v1/events/parse" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "text": "내일 오후 3시에 강남역에서 김과장과 프로젝트 회의",
    "timezone": "Asia/Seoul"
  }'
```

**예상 응답:**
```json
{
  "success": true,
  "parsed_event": {
    "title": "김과장과 프로젝트 회의",
    "start_at": "2024-08-20T15:00:00+09:00",
    "end_at": "2024-08-20T16:00:00+09:00",
    "location": "강남역",
    "category": "work",
    "confidence": 0.92
  },
  "confidence_score": 0.92,
  "suggestions": ["회의 안건을 미리 준비해보세요"]
}
```

### 4. 데이터베이스 관리 도구 사용

**PgAdmin 접속:**
```
http://localhost:5050
```
- 이메일: `admin@timetree.dev`
- 비밀번호: `admin123`

**서버 연결 설정:**
- Host: `postgres`
- Port: `5432`
- Database: `timetree_creator`
- Username: `app_user`
- Password: `dev_password_123`

---

## 🚀 프로덕션 배포 (Ansible)

### 1. 서버 준비

**Ubuntu 20.04+ 서버 필요:**
```bash
# 서버 접속 확인
ssh ubuntu@your-server-ip

# 기본 패키지 업데이트
sudo apt update && sudo apt upgrade -y
```

### 2. Ansible 설치

**로컬 머신에 Ansible 설치:**

**macOS:**
```bash
brew install ansible
```

**Ubuntu/Debian:**
```bash
sudo apt install ansible
```

### 3. 서버 정보 설정

```bash
# Ansible 인벤토리 파일 수정
nano ansible/inventory/hosts.yml
```

**hosts.yml 예시:**
```yaml
all:
  vars:
    project_name: "timetree-creator"
    environment: "production"
    
  children:
    web_servers:
      hosts:
        web1:
          ansible_host: 192.168.1.10  # 실제 서버 IP로 변경
          ansible_port: 22
          
    database_servers:
      hosts:
        db1:
          ansible_host: 192.168.1.20  # 실제 DB 서버 IP로 변경
          
    cache_servers:
      hosts:
        cache1:
          ansible_host: 192.168.1.30  # 실제 Redis 서버 IP
```

### 4. SSH 키 설정

```bash
# SSH 키가 없는 경우 생성
ssh-keygen -t rsa -b 4096 -C "your-email@example.com"

# 서버에 공개키 복사
ssh-copy-id ubuntu@your-server-ip
```

### 5. 배포 실행

```bash
# Ansible 디렉토리로 이동
cd ansible

# 연결 테스트
ansible all -m ping

# 전체 배포 실행
ansible-playbook site.yml

# 특정 서버만 배포
ansible-playbook site.yml --limit web_servers
```

### 6. 배포 후 확인

```bash
# 서버 상태 확인
ansible all -m shell -a "docker ps"

# 애플리케이션 상태 확인
curl http://your-server-ip/api/health/
```

---

## 🛠 트러블슈팅

### 1. Docker 관련 문제

**문제: 포트가 이미 사용 중**
```bash
# 사용 중인 포트 확인
lsof -i :8000
lsof -i :5432

# 기존 컨테이너 중지
docker-compose down

# 모든 컨테이너 강제 삭제
docker system prune -a
```

**문제: 권한 오류**
```bash
# Docker 그룹에 사용자 추가
sudo usermod -aG docker $USER

# 로그아웃 후 다시 로그인 또는
newgrp docker
```

### 2. 데이터베이스 연결 문제

**문제: PostgreSQL 연결 실패**
```bash
# 데이터베이스 컨테이너 로그 확인
docker-compose logs postgres

# 컨테이너 재시작
docker-compose restart postgres

# 데이터베이스 초기화
docker-compose down -v  # 주의: 데이터 삭제됨
docker-compose up -d
```

### 3. API 키 관련 문제

**문제: OpenAI API 호출 실패**
```bash
# API 키 확인
echo $OPENAI_API_KEY

# 키가 올바른지 직접 테스트
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
  https://api.openai.com/v1/models
```

**문제: TimeTree 연동 실패**
- TimeTree Developer Console에서 리디렉션 URI 확인
- 클라이언트 ID와 시크릿이 정확한지 확인

### 4. 로그 확인 방법

```bash
# 백엔드 애플리케이션 로그
docker-compose logs -f backend

# 특정 시간대 로그만 확인
docker-compose logs --since="1h" backend

# 로그 파일 직접 확인
tail -f logs/app.log
```

### 5. 개발 환경 초기화

```bash
# 모든 컨테이너와 볼륨 삭제 (데이터 삭제됨!)
docker-compose down -v

# 이미지도 삭제
docker-compose down --rmi all -v

# 처음부터 다시 시작
docker-compose up --build -d
```

---

## 📚 추가 도움말

### 유용한 명령어들

```bash
# 실행 중인 컨테이너 목록
docker ps

# 컨테이너 내부 접속
docker-compose exec backend bash
docker-compose exec postgres psql -U app_user -d timetree_creator

# 로그 실시간 확인
docker-compose logs -f

# 특정 서비스만 재시작
docker-compose restart backend

# 리소스 사용량 확인
docker stats
```

### 개발 시 유용한 팁

1. **코드 변경 시 자동 재시작**: 백엔드는 `--reload` 옵션으로 파일 변경 시 자동 재시작됩니다.

2. **데이터베이스 스키마 변경**: 
   ```bash
   # 마이그레이션 파일 생성
   docker-compose exec backend alembic revision --autogenerate -m "description"
   
   # 마이그레이션 적용
   docker-compose exec backend alembic upgrade head
   ```

3. **테스트 실행**:
   ```bash
   docker-compose exec backend pytest
   docker-compose exec backend pytest tests/test_events.py -v
   ```

---

## 🎉 완료!

이제 TimeTree Event Creator가 성공적으로 실행되었습니다!

- **API 서버**: http://localhost:8000
- **API 문서**: http://localhost:8000/docs  
- **데이터베이스 관리**: http://localhost:5050

**다음 단계:**
1. 실제 OpenAI API 키와 TimeTree 인증 정보 설정
2. 자연어 파싱 기능 테스트
3. TimeTree 연동 테스트
4. 프론트엔드 개발 (선택사항)

문제가 발생하면 위의 트러블슈팅 섹션을 참고하거나 로그를 확인해주세요!