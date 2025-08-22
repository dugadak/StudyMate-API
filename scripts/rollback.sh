#!/bin/bash

# StudyMate API 롤백 스크립트
# 배포 실패 시 이전 버전으로 빠르게 복구

set -e

echo "=========================================="
echo "StudyMate API Emergency Rollback"
echo "=========================================="

# 설정
APP_DIR="/home/ec2-user/apps/StudyMate-API"
BACKUP_DIR="/home/ec2-user/apps/backups"
LOG_DIR="/home/ec2-user/apps/logs"
CURRENT_PORT_FILE="$APP_DIR/.current_port"

# 색상 출력
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 로그 함수
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 현재 포트 확인
get_current_port() {
    if [ -f "$CURRENT_PORT_FILE" ]; then
        cat "$CURRENT_PORT_FILE"
    else
        echo "8000"
    fi
}

# 이전 포트 확인
get_previous_port() {
    current=$(get_current_port)
    if [ "$current" == "8000" ]; then
        echo "8001"
    else
        echo "8000"
    fi
}

# 백업 복구
restore_backup() {
    log_info "백업 복구 시작..."
    
    if [ ! -d "$BACKUP_DIR" ]; then
        log_error "백업 디렉토리가 없습니다!"
        return 1
    fi
    
    # 최신 백업 찾기
    latest_backup=$(ls -t "$BACKUP_DIR"/*.tar.gz 2>/dev/null | head -1)
    
    if [ -z "$latest_backup" ]; then
        log_error "백업 파일을 찾을 수 없습니다!"
        return 1
    fi
    
    log_info "백업 파일 발견: $latest_backup"
    
    # 현재 코드 임시 보관
    timestamp=$(date +%Y%m%d_%H%M%S)
    temp_dir="/tmp/studymate_failed_$timestamp"
    mkdir -p "$temp_dir"
    
    log_info "현재 실패한 코드를 임시 보관 중..."
    cp -r "$APP_DIR" "$temp_dir/" 2>/dev/null || true
    
    # 백업 복구
    log_info "백업 복구 중..."
    cd /
    tar -xzf "$latest_backup" 2>/dev/null || {
        log_error "백업 복구 실패!"
        return 1
    }
    
    log_info "백업 복구 완료"
    return 0
}

# 이전 포트로 전환
switch_to_previous_port() {
    local previous_port=$(get_previous_port)
    local session_name="studymate_$previous_port"
    
    log_info "이전 포트로 전환 중 (포트: $previous_port)..."
    
    # 이전 세션이 살아있는지 확인
    if tmux has-session -t "$session_name" 2>/dev/null; then
        log_info "이전 세션이 활성 상태입니다"
        
        # Nginx를 이전 포트로 전환
        update_nginx "$previous_port"
        
        # 포트 정보 업데이트
        echo "$previous_port" > "$CURRENT_PORT_FILE"
        
        log_info "이전 버전으로 전환 완료"
        return 0
    else
        log_warn "이전 세션이 없습니다. 새로 시작합니다..."
        return 1
    fi
}

# Nginx 설정 업데이트
update_nginx() {
    local port=$1
    
    log_info "Nginx를 포트 $port로 설정 중..."
    
    sudo tee /etc/nginx/conf.d/studymate.conf > /dev/null << EOF
upstream studymate_backend {
    server 127.0.0.1:$port;
    keepalive 32;
}

server {
    listen 80;
    server_name _;
    
    client_max_body_size 10M;
    keepalive_timeout 65;
    keepalive_requests 100;
    
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript 
               application/x-javascript application/xml+rss 
               application/javascript application/json;
    
    location /static/ {
        alias $APP_DIR/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    location /media/ {
        alias $APP_DIR/media/;
        expires 7d;
        add_header Cache-Control "public";
    }
    
    location / {
        proxy_pass http://studymate_backend;
        proxy_http_version 1.1;
        proxy_set_header Host \$http_host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Connection "";
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
    }
    
    location /health/ {
        proxy_pass http://studymate_backend/health/;
        access_log off;
    }
}
EOF
    
    sudo nginx -t && sudo systemctl reload nginx
    log_info "Nginx 설정 완료"
}

# 긴급 재시작
emergency_restart() {
    log_info "긴급 재시작 중..."
    
    cd "$APP_DIR"
    source venv/bin/activate
    
    # 모든 tmux 세션 종료
    tmux kill-session -t studymate_8000 2>/dev/null || true
    tmux kill-session -t studymate_8001 2>/dev/null || true
    
    # 기본 포트로 재시작
    local port=8000
    local session_name="studymate_$port"
    
    tmux new-session -d -s "$session_name" -c "$APP_DIR" "
        source venv/bin/activate
        gunicorn studymate_api.wsgi:application \
            --bind 127.0.0.1:$port \
            --workers 2 \
            --threads 2 \
            --worker-class sync \
            --timeout 30 \
            --access-logfile $LOG_DIR/access.log \
            --error-logfile $LOG_DIR/error.log \
            --log-level info
    "
    
    sleep 5
    
    # Nginx 설정
    update_nginx "$port"
    echo "$port" > "$CURRENT_PORT_FILE"
    
    log_info "긴급 재시작 완료"
}

# 헬스 체크
health_check() {
    local port=$1
    local max_attempts=10
    local attempt=0
    
    log_info "헬스 체크 중..."
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -f -s -o /dev/null "http://127.0.0.1:$port/health/"; then
            log_info "헬스 체크 성공!"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    log_error "헬스 체크 실패!"
    return 1
}

# 로그 분석
analyze_logs() {
    log_info "최근 에러 로그 분석 중..."
    
    if [ -f "$LOG_DIR/error.log" ]; then
        echo "========== 최근 에러 로그 =========="
        tail -n 50 "$LOG_DIR/error.log" | grep -E "ERROR|CRITICAL|Exception|Traceback" || echo "에러 없음"
        echo "===================================="
    fi
}

# 메인 롤백 프로세스
main() {
    log_error "=========================================="
    log_error "긴급 롤백 시작: $(date)"
    log_error "=========================================="
    
    # 1. 먼저 이전 포트로 전환 시도
    if switch_to_previous_port; then
        log_info "이전 버전으로 전환 성공"
        
        # 헬스 체크
        if health_check "$(get_previous_port)"; then
            log_info "롤백 성공!"
        else
            log_error "이전 버전도 문제가 있습니다. 백업 복구를 시도합니다..."
            restore_backup && emergency_restart
        fi
    else
        # 2. 백업에서 복구
        log_info "백업에서 복구를 시도합니다..."
        if restore_backup; then
            emergency_restart
        else
            log_error "백업 복구 실패. 수동 개입이 필요합니다!"
            analyze_logs
            exit 1
        fi
    fi
    
    # 3. 최종 상태 확인
    current_port=$(get_current_port)
    if health_check "$current_port"; then
        log_info "=========================================="
        log_info "롤백 완료! 서비스가 포트 $current_port에서 정상 작동 중"
        log_info "완료 시간: $(date)"
        log_info "=========================================="
        
        # 로그 분석
        analyze_logs
    else
        log_error "=========================================="
        log_error "롤백 실패! 수동 개입이 필요합니다"
        log_error "다음 명령어로 상태를 확인하세요:"
        log_error "  tmux ls"
        log_error "  tmux attach -t studymate_8000"
        log_error "  tail -f $LOG_DIR/error.log"
        log_error "=========================================="
        exit 1
    fi
}

# 스크립트 실행
main "$@"