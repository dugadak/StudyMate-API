#!/bin/bash

# StudyMate API HTTPS 설정 스크립트
# AWS EC2 Amazon Linux 2용

echo "🔐 StudyMate API HTTPS 설정 시작..."

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 서버 IP
SERVER_IP="54.161.77.144"

# 1. 시스템 업데이트
echo -e "${YELLOW}📦 시스템 패키지 업데이트 중...${NC}"
sudo yum update -y

# 2. Certbot 설치
echo -e "${YELLOW}🔧 Certbot 설치 중...${NC}"
sudo amazon-linux-extras install epel -y
sudo yum install certbot python3-certbot-nginx -y

# 3. Nginx 설정 백업
echo -e "${YELLOW}💾 Nginx 설정 백업 중...${NC}"
sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup.$(date +%Y%m%d)

# 4. Nginx 설정 업데이트 (self-signed certificate로 시작)
echo -e "${YELLOW}🔨 Nginx HTTPS 설정 생성 중...${NC}"

# Self-signed certificate 생성 (임시)
sudo mkdir -p /etc/nginx/ssl
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/studymate.key \
    -out /etc/nginx/ssl/studymate.crt \
    -subj "/C=US/ST=State/L=City/O=StudyMate/CN=$SERVER_IP"

# Nginx HTTPS 설정 파일 생성
cat > /tmp/studymate-https.conf << 'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name 54.161.77.144;

    # HTTP to HTTPS 리다이렉트
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name 54.161.77.144;

    # SSL 인증서 설정
    ssl_certificate /etc/nginx/ssl/studymate.crt;
    ssl_certificate_key /etc/nginx/ssl/studymate.key;

    # SSL 설정
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # 보안 헤더
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # API 프록시 설정
    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # CORS 헤더
        add_header 'Access-Control-Allow-Origin' '*' always;
        add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
        add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization' always;
        add_header 'Access-Control-Expose-Headers' 'Content-Length,Content-Range' always;
        
        # OPTIONS 요청 처리
        if ($request_method = 'OPTIONS') {
            add_header 'Access-Control-Allow-Origin' '*';
            add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS';
            add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization';
            add_header 'Access-Control-Max-Age' 1728000;
            add_header 'Content-Type' 'text/plain; charset=utf-8';
            add_header 'Content-Length' 0;
            return 204;
        }
    }

    # 상태 체크 엔드포인트
    location /health {
        proxy_pass http://localhost:8000/health;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

# Nginx 설정 적용
sudo cp /tmp/studymate-https.conf /etc/nginx/conf.d/studymate-https.conf

# 5. Nginx 설정 테스트
echo -e "${YELLOW}🔍 Nginx 설정 테스트 중...${NC}"
sudo nginx -t

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Nginx 설정 테스트 성공!${NC}"
    
    # 6. Nginx 재시작
    echo -e "${YELLOW}🔄 Nginx 재시작 중...${NC}"
    sudo systemctl restart nginx
    
    # 7. 방화벽 설정
    echo -e "${YELLOW}🔥 방화벽 설정 중...${NC}"
    sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
    sudo service iptables save 2>/dev/null || true
    
    echo -e "${GREEN}✅ HTTPS 설정 완료!${NC}"
    echo -e "${GREEN}🔐 서버 주소: https://$SERVER_IP${NC}"
    echo -e "${YELLOW}⚠️  주의: 현재 self-signed certificate를 사용 중입니다.${NC}"
    echo -e "${YELLOW}    프로덕션 환경에서는 정식 인증서를 사용하세요.${NC}"
    
    # 8. 연결 테스트
    echo -e "\n${YELLOW}🧪 HTTPS 연결 테스트 중...${NC}"
    sleep 2
    curl -k https://$SERVER_IP/health 2>/dev/null && echo -e "${GREEN}✅ HTTPS 연결 성공!${NC}" || echo -e "${RED}❌ HTTPS 연결 실패${NC}"
    
else
    echo -e "${RED}❌ Nginx 설정 테스트 실패!${NC}"
    echo -e "${YELLOW}설정 파일을 확인해주세요: /etc/nginx/conf.d/studymate-https.conf${NC}"
    exit 1
fi

echo -e "\n${GREEN}🎉 HTTPS 설정이 완료되었습니다!${NC}"
echo -e "${YELLOW}Flutter 앱에서 https://$SERVER_IP 로 접속하세요.${NC}"