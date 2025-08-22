# 🚀 AWS EC2 프리티어 설정 가이드

## 📋 사전 준비
- AWS 계정 (프리티어 자격)
- GitHub 저장소: https://github.com/dugadak/StudyMate-API

---

## 1️⃣ AWS EC2 인스턴스 생성

### AWS Console 접속
1. https://console.aws.amazon.com 로그인
2. 리전을 **서울 (ap-northeast-2)** 로 변경

### EC2 인스턴스 시작
1. EC2 Dashboard → "인스턴스 시작" 클릭

2. **이름 및 태그**
   - 이름: `StudyMate-API-Server`

3. **AMI 선택** (프리티어)
   - Amazon Linux 2023 AMI (무료 티어 사용 가능)
   - 64비트 (x86)

4. **인스턴스 유형**
   - **t2.micro** (프리티어 - vCPU 1개, 메모리 1GB)

5. **키 페어**
   - "새 키 페어 생성" 클릭
   - 키 페어 이름: `studymate-key`
   - 키 페어 유형: RSA
   - 프라이빗 키 파일 형식: .pem
   - 다운로드 후 안전한 곳에 보관!

6. **네트워크 설정**
   - VPC: 기본값
   - 서브넷: 기본값
   - 퍼블릭 IP 자동 할당: **활성화**
   - 보안 그룹 생성:
     ```
     이름: studymate-sg
     설명: StudyMate API Security Group
     
     인바운드 규칙:
     - SSH: 포트 22, 소스 0.0.0.0/0 (또는 내 IP)
     - HTTP: 포트 80, 소스 0.0.0.0/0
     - HTTPS: 포트 443, 소스 0.0.0.0/0
     - Custom TCP: 포트 8000, 소스 0.0.0.0/0 (테스트용)
     ```

7. **스토리지 구성**
   - 8GB gp3 (프리티어 한도: 30GB까지 무료)
   - 종료 시 삭제: 체크

8. **고급 세부 정보**
   - 종료 보호: 활성화 (실수 방지)
   - 세부 모니터링: 비활성화 (추가 비용 방지)

9. "인스턴스 시작" 클릭

---

## 2️⃣ Elastic IP 할당 (선택사항)

고정 IP가 필요한 경우:
1. EC2 → 네트워크 및 보안 → 탄력적 IP
2. "탄력적 IP 주소 할당" 클릭
3. "할당" 클릭
4. 할당된 IP 선택 → 작업 → "탄력적 IP 주소 연결"
5. 인스턴스 선택 → "연결"

⚠️ **주의**: 탄력적 IP는 EC2에 연결되어 있을 때만 무료. 미사용 시 시간당 요금 부과!

---

## 3️⃣ EC2 접속 및 초기 설정

### SSH 접속
```bash
# 키 파일 권한 설정
chmod 400 ~/Downloads/studymate-key.pem

# SSH 접속
ssh -i ~/Downloads/studymate-key.pem ec2-user@[EC2-퍼블릭-IP]
```

### 초기 설정 스크립트 실행
```bash
# 스크립트 다운로드
curl -O https://raw.githubusercontent.com/dugadak/StudyMate-API/main/scripts/setup_ec2.sh

# 실행 권한 부여
chmod +x setup_ec2.sh

# 설정 실행
./setup_ec2.sh
```

---

## 4️⃣ 애플리케이션 설정

### 저장소 클론
```bash
cd ~/apps
git clone https://github.com/dugadak/StudyMate-API.git
cd StudyMate-API
```

### 환경 변수 설정
```bash
# .env 파일 생성
cp .env.example .env
nano .env

# 다음 항목들을 수정:
# - SECRET_KEY: 랜덤 문자열 생성 (python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
# - ALLOWED_HOSTS: EC2 퍼블릭 IP 추가
# - DATABASE_URL: SQLite 사용 (sqlite:///db.sqlite3) 또는 RDS 연결
```

### 가상환경 및 의존성 설치
```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

### Django 초기 설정
```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser  # 관리자 계정 생성
```

---

## 5️⃣ 첫 배포 실행

### 수동 배포
```bash
cd ~/apps/StudyMate-API
chmod +x scripts/*.sh
./scripts/deploy.sh
```

### 배포 확인
```bash
# tmux 세션 확인
tmux ls

# 프로세스 확인
ps aux | grep gunicorn

# 로그 확인
tail -f ~/apps/logs/error.log

# 헬스 체크
curl http://localhost:8000/health/
```

### 외부 접속 테스트
브라우저에서: `http://[EC2-퍼블릭-IP]/health/`

---

## 6️⃣ GitHub Secrets 설정

### GitHub 저장소에서:
1. Settings → Secrets and variables → Actions
2. "New repository secret" 클릭

### 필수 Secrets:

#### EC2_HOST
- EC2 퍼블릭 IP 또는 Elastic IP
- 예: `13.125.123.456`

#### EC2_PRIVATE_KEY
```bash
# 로컬에서 키 파일 내용 복사
cat ~/Downloads/studymate-key.pem
```
- 전체 내용 복사 (-----BEGIN RSA PRIVATE KEY----- 포함)

#### SLACK_WEBHOOK (선택)
- Slack 알림을 원하는 경우
- https://api.slack.com/messaging/webhooks 에서 생성

---

## 7️⃣ 자동 배포 테스트

### GitHub Actions 확인
1. 코드 변경 후 커밋
```bash
echo "# Deploy test" >> README.md
git add README.md
git commit -m "Test: 자동 배포 테스트"
git push origin main
```

2. GitHub → Actions 탭에서 배포 진행 상황 확인

---

## 🔍 트러블슈팅

### 1. SSH 접속 실패
```bash
# 보안 그룹 확인
# AWS Console → EC2 → 보안 그룹 → 인바운드 규칙
# SSH (22번 포트) 허용 확인

# 키 파일 권한 확인
ls -la ~/Downloads/studymate-key.pem
# 권한이 400이어야 함
```

### 2. 메모리 부족
```bash
# 스왑 파일 생성 (t2.micro용)
sudo dd if=/dev/zero of=/swapfile bs=128M count=16
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile swap swap defaults 0 0' | sudo tee -a /etc/fstab
```

### 3. 디스크 공간 부족
```bash
# 디스크 사용량 확인
df -h

# 불필요한 파일 정리
sudo yum clean all
rm -rf ~/apps/logs/*.log
```

### 4. Nginx 502 Bad Gateway
```bash
# Gunicorn 상태 확인
tmux attach -t studymate_8000

# Nginx 에러 로그
sudo tail -f /var/log/nginx/error.log
```

---

## 💰 비용 관리 팁

### 프리티어 한도
- EC2 t2.micro: 월 750시간 (1개 인스턴스 24/7 실행 가능)
- EBS 스토리지: 30GB
- 데이터 전송: 월 15GB

### 비용 절감 방법
1. **인스턴스 중지**: 사용하지 않을 때는 중지 (Stop)
2. **스냅샷 관리**: 오래된 스냅샷 삭제
3. **로그 정리**: 정기적으로 로그 파일 정리
4. **CloudWatch**: 상세 모니터링 비활성화

### 비용 모니터링
- AWS Budgets 설정: 월 $5 알림
- Cost Explorer 활용

---

## 📞 추가 지원

문제가 발생하면:
1. GitHub Issues: https://github.com/dugadak/StudyMate-API/issues
2. 로그 확인: `~/apps/logs/`
3. AWS 공식 문서: https://docs.aws.amazon.com

---

**작성일**: 2024년 12월
**버전**: 1.0.0