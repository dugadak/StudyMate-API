# 📚 StudyMate API 배포 가이드

## 🚀 AWS EC2 무중단 배포 시스템

### 📋 목차
- [아키텍처 개요](#-아키텍처-개요)
- [초기 설정](#-초기-설정)
- [CI/CD 파이프라인](#-cicd-파이프라인)
- [배포 프로세스](#-배포-프로세스)
- [모니터링 및 롤백](#-모니터링-및-롤백)
- [비용 최적화](#-비용-최적화)

---

## 🏗 아키텍처 개요

### 시스템 구성 (AWS 프리티어 최적화)
```
┌─────────────────────────────────────────────────────┐
│                   GitHub Repository                  │
│                  (StudyMate-API)                     │
└────────────────┬────────────────────────────────────┘
                 │ Push to main branch
                 ▼
┌─────────────────────────────────────────────────────┐
│              GitHub Actions CI/CD                    │
│         • Test → Build → Deploy → Health Check       │
└────────────────┬────────────────────────────────────┘
                 │ SSH Deploy
                 ▼
┌─────────────────────────────────────────────────────┐
│                  AWS EC2 Instance                    │
│                   (t2.micro - 프리티어)                │
│  ┌──────────────────────────────────────────────┐   │
│  │               Nginx (Port 80)                │   │
│  └────────────┬──────────┬──────────────────────┘   │
│               │          │                           │
│         Blue │          │ Green                      │
│         Port 8000      Port 8001                     │
│  ┌──────────────┐  ┌──────────────┐                │
│  │   Gunicorn   │  │   Gunicorn   │                │
│  │   (tmux)     │  │   (tmux)     │                │
│  └──────────────┘  └──────────────┘                │
│         │                │                           │
│  ┌────────────────────────────────┐                │
│  │    Django Application          │                │
│  │    + Redis (로컬)               │                │
│  └────────────────────────────────┘                │
└─────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│              AWS RDS (t3.micro)                      │
│              PostgreSQL Database                     │
└─────────────────────────────────────────────────────┘
```

---

## 🔧 초기 설정

### 1. EC2 인스턴스 준비

```bash
# SSH로 EC2 접속
ssh -i /path/to/your-key.pem ec2-user@your-ec2-ip

# 초기 설정 스크립트 실행
curl -O https://raw.githubusercontent.com/StudyMate-Company/StudyMate-API/main/scripts/setup_ec2.sh
chmod +x setup_ec2.sh
./setup_ec2.sh
```

### 2. 환경 변수 설정

```bash
cd ~/apps/StudyMate-API
cp .env.example .env
nano .env  # 실제 값으로 수정
```

### 3. GitHub Secrets 설정

GitHub 저장소 Settings → Secrets and variables → Actions에서 다음 시크릿 추가:

| Secret Name | Description | Example |
|------------|-------------|---------|
| `EC2_HOST` | EC2 퍼블릭 IP | `13.125.xxx.xxx` |
| `EC2_PRIVATE_KEY` | EC2 SSH 프라이빗 키 | `-----BEGIN RSA...` |
| `SLACK_WEBHOOK` | Slack 알림 URL (선택) | `https://hooks.slack...` |

---

## 🔄 CI/CD 파이프라인

### GitHub Actions 워크플로우

```yaml
# .github/workflows/deploy.yml
name: Deploy to AWS EC2

on:
  push:
    branches: [main]

jobs:
  test:
    # 테스트 실행
  deploy:
    # 무중단 배포
  rollback:
    # 실패 시 자동 롤백
```

### 배포 트리거
- `main` 브랜치에 push 또는 merge
- GitHub Actions 페이지에서 수동 실행

---

## 📦 배포 프로세스

### Blue-Green 무중단 배포

1. **코드 업데이트**
   ```bash
   git fetch --all
   git reset --hard origin/main
   ```

2. **의존성 설치**
   ```bash
   pip install -r requirements.txt --no-cache-dir
   ```

3. **마이그레이션**
   ```bash
   python manage.py migrate --noinput
   ```

4. **정적 파일 수집**
   ```bash
   python manage.py collectstatic --noinput
   ```

5. **새 인스턴스 시작** (Blue 또는 Green)
   ```bash
   tmux new-session -d -s studymate_8001 \
     "gunicorn studymate_api.wsgi:application --bind 127.0.0.1:8001"
   ```

6. **헬스 체크**
   ```bash
   curl http://127.0.0.1:8001/health/
   ```

7. **Nginx 전환**
   ```nginx
   upstream studymate_backend {
       server 127.0.0.1:8001;  # Green으로 전환
   }
   ```

8. **이전 인스턴스 종료**
   ```bash
   tmux kill-session -t studymate_8000
   ```

---

## 🔍 모니터링 및 롤백

### tmux 세션 관리

```bash
# 실행 중인 세션 확인
tmux ls

# 세션 접속
tmux attach -t studymate_8000

# 세션에서 나가기 (세션 유지)
Ctrl+B, D

# 로그 실시간 확인
tail -f ~/apps/logs/error.log
```

### 수동 배포

```bash
cd ~/apps/StudyMate-API
./scripts/deploy.sh
```

### 긴급 롤백

```bash
cd ~/apps/StudyMate-API
./scripts/rollback.sh
```

### 상태 확인

```bash
# 프로세스 확인
ps aux | grep gunicorn

# 포트 확인
sudo netstat -tlnp | grep :800

# Nginx 상태
sudo systemctl status nginx

# Redis 상태
sudo systemctl status redis6
```

---

## 💰 비용 최적화

### AWS 프리티어 활용

| 서비스 | 프리티어 제한 | 설정 |
|--------|-------------|------|
| EC2 | t2.micro 750시간/월 | 1개 인스턴스만 실행 |
| RDS | t3.micro 750시간/월 | 자동 백업 비활성화 |
| S3 | 5GB 스토리지 | 정적 파일용 |
| CloudWatch | 기본 메트릭 무료 | 상세 모니터링 OFF |

### 최적화 팁

1. **메모리 관리**
   - Gunicorn 워커 수: 2개
   - max-requests: 1000 (메모리 누수 방지)

2. **스토리지 절약**
   - pip install --no-cache-dir
   - 백업 3개만 유지
   - 로그 로테이션 설정

3. **대역폭 절약**
   - Gzip 압축 활성화
   - 정적 파일 캐싱 (30일)
   - CloudFront 사용 검토

---

## 🛠 트러블슈팅

### 일반적인 문제 해결

| 문제 | 원인 | 해결 방법 |
|------|------|----------|
| 502 Bad Gateway | Gunicorn 미실행 | `tmux ls`로 확인 후 재시작 |
| 메모리 부족 | 워커 과다 | 워커 수 감소 (2개) |
| 디스크 가득 | 로그 누적 | 로그 정리: `rm ~/apps/logs/*.log` |
| 배포 실패 | 권한 문제 | `chmod +x scripts/*.sh` |

### 로그 위치

```bash
# 애플리케이션 로그
~/apps/logs/error.log
~/apps/logs/access.log

# Nginx 로그
/var/log/nginx/error.log
/var/log/nginx/access.log

# 시스템 로그
journalctl -u nginx
journalctl -u redis6
```

---

## 📝 체크리스트

### 배포 전
- [ ] 로컬에서 테스트 완료
- [ ] requirements.txt 업데이트
- [ ] 마이그레이션 파일 생성
- [ ] .env 설정 확인

### 배포 후
- [ ] 헬스 체크 통과
- [ ] 주요 API 엔드포인트 테스트
- [ ] 로그 에러 확인
- [ ] 성능 모니터링

---

## 🆘 지원

### 연락처
- 이슈: [GitHub Issues](https://github.com/StudyMate-Company/StudyMate-API/issues)
- 이메일: devops@studymate.com

### 유용한 명령어

```bash
# 시스템 리소스 확인
htop

# 디스크 사용량
df -h

# 메모리 사용량
free -m

# 네트워크 연결
ss -tulpn

# 프로세스 트리
pstree -p
```

---

## 🔐 보안 권장사항

1. **SSH 키 관리**
   - 프라이빗 키는 안전하게 보관
   - GitHub Secrets에만 저장

2. **환경 변수**
   - .env 파일은 절대 커밋하지 않음
   - 프로덕션 시크릿은 별도 관리

3. **방화벽 설정**
   - 필요한 포트만 오픈 (80, 443, 22)
   - IP 화이트리스트 설정 권장

4. **정기 업데이트**
   ```bash
   sudo yum update -y
   pip list --outdated
   ```

---

**Last Updated**: 2024년 12월
**Version**: 1.0.0