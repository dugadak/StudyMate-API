#!/bin/bash

# StudyMate API EC2 초기 설정 스크립트
# 이 스크립트는 새로운 EC2 인스턴스에서 한 번만 실행됩니다.

set -e  # 에러 발생 시 스크립트 중단

echo "=========================================="
echo "StudyMate API EC2 Setup Script"
echo "=========================================="

# 시스템 업데이트
echo "1. 시스템 패키지 업데이트 중..."
sudo yum update -y

# 필수 패키지 설치
echo "2. 필수 패키지 설치 중..."
sudo yum install -y git python3 python3-pip python3-devel
sudo yum install -y postgresql15 postgresql15-devel
sudo yum install -y nginx
sudo yum install -y redis6
sudo yum install -y tmux htop

# Python 3.10 설치 (Amazon Linux 2023은 기본적으로 3.9가 설치되어 있음)
echo "3. Python 3.10 설치 중..."
sudo yum install -y python3.10 python3.10-pip python3.10-devel

# pip 업그레이드
echo "4. pip 업그레이드 중..."
python3.10 -m pip install --upgrade pip

# 가상환경 도구 설치
echo "5. virtualenv 설치 중..."
python3.10 -m pip install virtualenv

# 프로젝트 디렉토리 생성
echo "6. 프로젝트 디렉토리 생성 중..."
mkdir -p ~/apps
cd ~/apps

# Git 저장소 클론
echo "7. StudyMate API 저장소 클론 중..."
if [ ! -d "StudyMate-API" ]; then
    git clone https://github.com/StudyMate-Company/StudyMate-API.git
fi

cd StudyMate-API

# 가상환경 생성 및 활성화
echo "8. Python 가상환경 생성 중..."
python3.10 -m venv venv
source venv/bin/activate

# 의존성 설치
echo "9. Python 패키지 설치 중..."
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn

# 로그 디렉토리 생성
echo "10. 로그 디렉토리 생성 중..."
mkdir -p ~/apps/logs
mkdir -p ~/apps/StudyMate-API/logs
mkdir -p ~/apps/StudyMate-API/staticfiles
mkdir -p ~/apps/StudyMate-API/media

# Redis 서비스 시작
echo "11. Redis 서비스 시작 중..."
sudo systemctl start redis6
sudo systemctl enable redis6

# Nginx 설정
echo "12. Nginx 설정 중..."
sudo systemctl start nginx
sudo systemctl enable nginx

# 방화벽 설정
echo "13. 방화벽 설정 중..."
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload

# 환경 변수 파일 생성 안내
echo "14. 환경 변수 설정 필요..."
echo "=========================================="
echo "!!! 중요 !!!"
echo ".env 파일을 생성하고 필요한 환경 변수를 설정하세요:"
echo "cp .env.example .env"
echo "nano .env"
echo "=========================================="

# tmux 설정 파일 생성
echo "15. tmux 설정 파일 생성 중..."
cat > ~/.tmux.conf << 'EOF'
# 마우스 지원 활성화
set -g mouse on

# 상태바 설정
set -g status-bg green
set -g status-fg black
set -g status-left '#[fg=black]#S '
set -g status-right '#[fg=black]%Y-%m-%d %H:%M '

# 윈도우 인덱스를 1부터 시작
set -g base-index 1
setw -g pane-base-index 1

# 히스토리 크기 증가
set -g history-limit 10000
EOF

echo "=========================================="
echo "EC2 초기 설정이 완료되었습니다!"
echo ""
echo "다음 단계:"
echo "1. .env 파일 생성 및 설정"
echo "2. 데이터베이스 마이그레이션 실행"
echo "3. 정적 파일 수집"
echo "4. deploy.sh 스크립트로 애플리케이션 시작"
echo "=========================================="