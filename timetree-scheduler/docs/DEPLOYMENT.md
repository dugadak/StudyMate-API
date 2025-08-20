# 🚀 배포 가이드

> **TimeTree Scheduler를 프로덕션 환경에 배포하는 방법**

## 📋 목차
- [배포 전 체크리스트](#-배포-전-체크리스트)
- [로컬 개발 환경](#-로컬-개발-환경)
- [Docker로 배포](#-docker로-배포)
- [클라우드 배포](#-클라우드-배포)
- [환경 설정](#-환경-설정)
- [모니터링 및 로그](#-모니터링-및-로그)
- [백업 및 복구](#-백업-및-복구)

---

## ✅ 배포 전 체크리스트

### 필수 요구사항
- [ ] **TimeTree 개발자 계정** 및 앱 등록
- [ ] **OpenAI API 키** 발급
- [ ] **PostgreSQL 데이터베이스** 준비
- [ ] **도메인 및 SSL 인증서** (프로덕션)
- [ ] **환경 변수** 설정 완료

### 권장 사양

#### 최소 사양
```
- CPU: 2 코어
- RAM: 4GB
- 디스크: 20GB SSD
- 네트워크: 1Gbps
```

#### 권장 사양 (프로덕션)
```
- CPU: 4 코어
- RAM: 8GB
- 디스크: 50GB SSD
- 네트워크: 10Gbps
- 로드밸런서: 필수
```

---

## 💻 로컬 개발 환경

### 1. 저장소 클론
```bash
git clone https://github.com/your-username/timetree-scheduler.git
cd timetree-scheduler
```

### 2. 환경 변수 설정
```bash
# 환경 변수 파일 복사
cp .env.example .env

# 필수 값들 입력
nano .env
```

### 3. 의존성 설치
```bash
# 백엔드 의존성
cd backend
pip install -r requirements.txt

# 프론트엔드 의존성  
cd ../frontend
npm install
```

### 4. 데이터베이스 설정
```bash
# PostgreSQL 설치 (macOS)
brew install postgresql
brew services start postgresql

# 데이터베이스 생성
createdb timetree_scheduler

# 마이그레이션 실행
cd ../backend
alembic upgrade head
```

### 5. 개발 서버 실행
```bash
# 터미널 1: 백엔드
cd backend
uvicorn main:app --reload --port 8000

# 터미널 2: 프론트엔드
cd frontend  
npm run dev
```

### 6. 접속 확인
```
Frontend: http://localhost:3000
Backend API: http://localhost:8000
API Docs: http://localhost:8000/docs
```

---

## 🐳 Docker로 배포

### 단일 서버 배포 (Docker Compose)

#### 1. 환경 설정
```bash
# 프로덕션 환경 변수 설정
cp .env.example .env.production
nano .env.production

# 필수 값들 설정
ENVIRONMENT=production
DATABASE_URL=postgresql://user:pass@db:5432/timetree_scheduler
REDIS_URL=redis://redis:6379/0
```

#### 2. Docker Compose 실행
```bash
# 프로덕션 빌드 및 실행
docker-compose -f docker-compose.prod.yml up -d

# 로그 확인
docker-compose logs -f
```

#### 3. 초기 설정
```bash
# 데이터베이스 마이그레이션
docker-compose exec backend alembic upgrade head

# 관리자 계정 생성 (선택사항)
docker-compose exec backend python scripts/create_admin.py
```

### Docker 이미지 수동 빌드

#### 백엔드 이미지
```bash
cd backend
docker build -t timetree-scheduler-backend:latest .
docker run -p 8000:8000 --env-file ../.env.production timetree-scheduler-backend:latest
```

#### 프론트엔드 이미지
```bash
cd frontend
docker build -t timetree-scheduler-frontend:latest .
docker run -p 3000:3000 timetree-scheduler-frontend:latest
```

---

## ☁️ 클라우드 배포

### AWS ECS + Fargate

#### 1. Terraform으로 인프라 구성
```bash
cd infra/terraform

# Terraform 초기화
terraform init

# 변수 설정
cp variables.tf.example variables.tf
nano variables.tf

# 배포 계획 확인
terraform plan

# 인프라 생성
terraform apply
```

#### 2. ECR에 이미지 푸시
```bash
# AWS CLI 로그인
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin YOUR_ACCOUNT.dkr.ecr.us-west-2.amazonaws.com

# 이미지 태그 및 푸시
docker tag timetree-scheduler-backend:latest YOUR_ACCOUNT.dkr.ecr.us-west-2.amazonaws.com/timetree-scheduler-backend:latest
docker push YOUR_ACCOUNT.dkr.ecr.us-west-2.amazonaws.com/timetree-scheduler-backend:latest

docker tag timetree-scheduler-frontend:latest YOUR_ACCOUNT.dkr.ecr.us-west-2.amazonaws.com/timetree-scheduler-frontend:latest  
docker push YOUR_ACCOUNT.dkr.ecr.us-west-2.amazonaws.com/timetree-scheduler-frontend:latest
```

#### 3. ECS 서비스 배포
```bash
# ECS 클러스터에 서비스 배포
aws ecs update-service --cluster timetree-scheduler --service backend --force-new-deployment
aws ecs update-service --cluster timetree-scheduler --service frontend --force-new-deployment
```

### Google Cloud Run

#### 1. 프로젝트 설정
```bash
# Google Cloud SDK 설치 및 로그인
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

#### 2. 이미지 빌드 및 배포
```bash
# 백엔드 배포
cd backend
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/timetree-scheduler-backend
gcloud run deploy backend --image gcr.io/YOUR_PROJECT_ID/timetree-scheduler-backend --platform managed --region us-central1

# 프론트엔드 배포
cd ../frontend
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/timetree-scheduler-frontend
gcloud run deploy frontend --image gcr.io/YOUR_PROJECT_ID/timetree-scheduler-frontend --platform managed --region us-central1
```

### Vercel (프론트엔드만)

#### 1. Vercel CLI 설치
```bash
npm install -g vercel
```

#### 2. 프론트엔드 배포
```bash
cd frontend
vercel --prod
```

#### 3. 환경 변수 설정
```bash
# Vercel 대시보드에서 환경 변수 설정
NEXT_PUBLIC_API_URL=https://your-backend-api.com
```

---

## ⚙️ 환경 설정

### 프로덕션 환경 변수

#### 필수 환경 변수
```bash
# 애플리케이션 설정
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=your-super-secret-production-key-32-chars-long
ENCRYPTION_KEY=your-32-byte-encryption-key-for-tokens

# 데이터베이스
DATABASE_URL=postgresql://user:password@host:5432/database
DATABASE_URL_TEST=postgresql://user:password@host:5432/test_database

# TimeTree API
TIMETREE_CLIENT_ID=your_production_client_id
TIMETREE_CLIENT_SECRET=your_production_client_secret
TIMETREE_REDIRECT_URI=https://yourdomain.com/auth/timetree/callback

# OpenAI API
OPENAI_API_KEY=your_openai_production_api_key
OPENAI_MODEL=gpt-4o

# Redis (선택사항)
REDIS_URL=redis://redis-host:6379/0

# 로깅 및 모니터링
LOG_LEVEL=INFO
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id

# CORS 설정
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

#### SSL/TLS 설정
```bash
# Let's Encrypt SSL 인증서 (무료)
sudo apt install certbot
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# SSL 인증서 경로
SSL_CERT_PATH=/etc/letsencrypt/live/yourdomain.com/fullchain.pem
SSL_KEY_PATH=/etc/letsencrypt/live/yourdomain.com/privkey.pem
```

### Nginx 설정 (리버스 프록시)

#### `/etc/nginx/sites-available/timetree-scheduler`
```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # SSL 설정
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # 보안 헤더
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # 프론트엔드 (Next.js)
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # 백엔드 API
    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # CORS 헤더
        add_header Access-Control-Allow-Origin https://yourdomain.com;
        add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS";
        add_header Access-Control-Allow-Headers "Authorization, Content-Type";
    }

    # 정적 파일 캐싱
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

---

## 📊 모니터링 및 로그

### 로그 설정

#### 구조화된 로그 (JSON 형태)
```bash
# 로그 파일 위치
/var/log/timetree-scheduler/
├── app.log          # 애플리케이션 로그
├── access.log       # API 접근 로그  
├── error.log        # 에러 로그
└── ai.log          # AI 요청 로그
```

#### 로그 로테이션 설정
```bash
# /etc/logrotate.d/timetree-scheduler
/var/log/timetree-scheduler/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 app app
    postrotate
        systemctl reload timetree-scheduler
    endscript
}
```

### Prometheus 메트릭
```bash
# 메트릭 엔드포인트
GET /metrics

# 주요 메트릭
- http_requests_total
- http_request_duration_seconds
- ai_requests_total
- timetree_api_requests_total
- database_connections_active
- memory_usage_bytes
```

### Grafana 대시보드
```bash
# 주요 대시보드 패널
- API 응답 시간
- 요청 성공률
- AI 파싱 정확도
- TimeTree API 상태
- 시스템 리소스 사용률
```

### Sentry 에러 추적
```bash
# Sentry 설정
SENTRY_DSN=https://your-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=production
SENTRY_RELEASE=v1.0.0

# 주요 추적 이벤트
- API 에러
- AI 파싱 실패
- TimeTree 연동 오류
- 데이터베이스 오류
```

---

## 💾 백업 및 복구

### 데이터베이스 백업

#### 자동 백업 스크립트
```bash
#!/bin/bash
# /scripts/backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/postgresql"
DB_NAME="timetree_scheduler"

# 백업 생성
pg_dump -h localhost -U postgres $DB_NAME | gzip > $BACKUP_DIR/backup_$DATE.sql.gz

# 30일 이상 된 백업 삭제
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +30 -delete

echo "Backup completed: backup_$DATE.sql.gz"
```

#### 크론탭 설정
```bash
# 매일 새벽 2시 백업
0 2 * * * /scripts/backup.sh
```

### 데이터베이스 복구
```bash
# 백업 파일 복구
gunzip -c backup_20240115_020000.sql.gz | psql -h localhost -U postgres timetree_scheduler
```

### 파일 백업 (AWS S3)
```bash
# 정적 파일 및 로그 백업
aws s3 sync /var/log/timetree-scheduler/ s3://your-backup-bucket/logs/
aws s3 sync /app/uploads/ s3://your-backup-bucket/uploads/
```

---

## 🔧 운영 명령어

### 시스템 상태 확인
```bash
# Docker Compose 서비스 상태
docker-compose ps

# 컨테이너 로그 확인
docker-compose logs -f backend
docker-compose logs -f frontend

# 리소스 사용량 확인
docker stats
```

### 서비스 재시작
```bash
# 전체 서비스 재시작
docker-compose restart

# 개별 서비스 재시작
docker-compose restart backend
docker-compose restart frontend
```

### 데이터베이스 마이그레이션
```bash
# 새로운 마이그레이션 생성
docker-compose exec backend alembic revision --autogenerate -m "description"

# 마이그레이션 적용
docker-compose exec backend alembic upgrade head

# 마이그레이션 롤백
docker-compose exec backend alembic downgrade -1
```

### 성능 튜닝
```bash
# 데이터베이스 연결 풀 설정
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=0

# Redis 메모리 최적화
REDIS_MAXMEMORY=1gb
REDIS_MAXMEMORY_POLICY=allkeys-lru

# Gunicorn 워커 설정
GUNICORN_WORKERS=4
GUNICORN_WORKER_CLASS=uvicorn.workers.UvicornWorker
```

---

## 🚨 장애 대응

### 주요 장애 시나리오

#### 1. API 응답 없음
```bash
# 서비스 상태 확인
docker-compose ps
curl -f http://localhost:8000/health

# 로그 확인
docker-compose logs backend | tail -100

# 재시작
docker-compose restart backend
```

#### 2. 데이터베이스 연결 실패
```bash
# PostgreSQL 상태 확인
docker-compose exec db pg_isready

# 연결 테스트
docker-compose exec backend python -c "from app.core.database import engine; print('DB OK')"
```

#### 3. TimeTree API 오류
```bash
# TimeTree API 상태 확인
curl -f https://timetreeapis.com/health

# 토큰 상태 확인
docker-compose exec backend python scripts/check_tokens.py
```

### 장애 복구 절차
1. **즉시 대응**: 서비스 재시작으로 임시 복구
2. **원인 분석**: 로그 분석 및 메트릭 확인
3. **근본 해결**: 코드 수정 또는 설정 변경
4. **재발 방지**: 모니터링 알람 설정

---

*🚀 성공적인 배포를 위해 단계별로 차근차근 진행하세요!*