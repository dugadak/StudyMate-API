#!/bin/bash

# StudyMate API 배포 스크립트
set -e

# 색상 코드
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 함수 정의
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 환경 변수 설정
ENVIRONMENT=${ENVIRONMENT:-production}
IMAGE_TAG=${IMAGE_TAG:-latest}
REGISTRY=${REGISTRY:-studymate}
IMAGE_NAME=${IMAGE_NAME:-api}
FULL_IMAGE="${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"

log_info "StudyMate API 배포 시작"
log_info "환경: ${ENVIRONMENT}"
log_info "이미지: ${FULL_IMAGE}"

# 필수 도구 확인
check_requirements() {
    log_info "필수 도구 확인 중..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker가 설치되지 않았습니다."
        exit 1
    fi
    
    if [[ "$ENVIRONMENT" == "kubernetes" ]]; then
        if ! command -v kubectl &> /dev/null; then
            log_error "kubectl이 설치되지 않았습니다."
            exit 1
        fi
    else
        if ! command -v docker-compose &> /dev/null; then
            log_error "docker-compose가 설치되지 않았습니다."
            exit 1
        fi
    fi
    
    log_success "필수 도구 확인 완료"
}

# Docker 이미지 빌드
build_image() {
    log_info "Docker 이미지 빌드 중..."
    
    if [[ "$ENVIRONMENT" == "development" ]]; then
        docker build -f Dockerfile.dev -t "${FULL_IMAGE}" .
    else
        docker build -f Dockerfile -t "${FULL_IMAGE}" .
    fi
    
    log_success "Docker 이미지 빌드 완료: ${FULL_IMAGE}"
}

# 이미지 푸시 (프로덕션 환경)
push_image() {
    if [[ "$ENVIRONMENT" == "production" || "$ENVIRONMENT" == "staging" ]]; then
        log_info "Docker 이미지 푸시 중..."
        docker push "${FULL_IMAGE}"
        log_success "Docker 이미지 푸시 완료"
    fi
}

# Docker Compose 배포
deploy_docker_compose() {
    log_info "Docker Compose로 배포 중..."
    
    if [[ "$ENVIRONMENT" == "development" ]]; then
        docker-compose -f docker-compose.dev.yml down --remove-orphans
        docker-compose -f docker-compose.dev.yml up -d --build
    else
        docker-compose down --remove-orphans
        docker-compose up -d --build
    fi
    
    log_success "Docker Compose 배포 완료"
}

# Kubernetes 배포
deploy_kubernetes() {
    log_info "Kubernetes로 배포 중..."
    
    # 네임스페이스 생성
    kubectl apply -f k8s/namespace.yaml
    
    # ConfigMap 및 Secret 적용
    kubectl apply -f k8s/configmap.yaml
    kubectl apply -f k8s/secrets.yaml
    
    # 데이터베이스 및 Redis 배포
    kubectl apply -f k8s/postgres.yaml
    kubectl apply -f k8s/redis.yaml
    
    # API 서비스 배포
    kubectl apply -f k8s/api.yaml
    
    # HPA 설정
    kubectl apply -f k8s/hpa.yaml
    
    # Ingress 설정
    kubectl apply -f k8s/ingress.yaml
    
    log_success "Kubernetes 배포 완료"
}

# 헬스체크
health_check() {
    log_info "헬스체크 수행 중..."
    
    if [[ "$ENVIRONMENT" == "kubernetes" ]]; then
        # Kubernetes 서비스 확인
        kubectl wait --for=condition=ready pod -l app=studymate-api -n studymate --timeout=300s
        
        # 포트 포워딩으로 헬스체크
        kubectl port-forward service/studymate-api-service 8000:8000 -n studymate &
        FORWARD_PID=$!
        sleep 5
        
        HEALTH_URL="http://localhost:8000/health/"
    else
        # Docker Compose 서비스 확인
        sleep 30  # 서비스 시작 대기
        HEALTH_URL="http://localhost:8000/health/"
    fi
    
    # 헬스체크 수행
    for i in {1..10}; do
        if curl -f "${HEALTH_URL}" > /dev/null 2>&1; then
            log_success "헬스체크 통과"
            if [[ "$ENVIRONMENT" == "kubernetes" ]]; then
                kill $FORWARD_PID 2>/dev/null || true
            fi
            return 0
        fi
        log_warning "헬스체크 시도 ${i}/10 실패, 10초 후 재시도..."
        sleep 10
    done
    
    log_error "헬스체크 실패"
    if [[ "$ENVIRONMENT" == "kubernetes" ]]; then
        kill $FORWARD_PID 2>/dev/null || true
    fi
    exit 1
}

# 배포 후 정리
cleanup() {
    log_info "배포 후 정리 중..."
    
    # 사용하지 않는 Docker 이미지 정리
    docker image prune -f
    
    log_success "정리 완료"
}

# 롤백 함수
rollback() {
    log_warning "롤백 수행 중..."
    
    if [[ "$ENVIRONMENT" == "kubernetes" ]]; then
        kubectl rollout undo deployment/studymate-api -n studymate
        kubectl rollout status deployment/studymate-api -n studymate
    else
        # 이전 버전으로 롤백 (이전 이미지 태그 필요)
        PREVIOUS_TAG=${PREVIOUS_TAG:-previous}
        PREVIOUS_IMAGE="${REGISTRY}/${IMAGE_NAME}:${PREVIOUS_TAG}"
        
        log_info "이전 이미지로 롤백: ${PREVIOUS_IMAGE}"
        docker tag "${PREVIOUS_IMAGE}" "${FULL_IMAGE}"
        
        if [[ "$ENVIRONMENT" == "development" ]]; then
            docker-compose -f docker-compose.dev.yml up -d
        else
            docker-compose up -d
        fi
    fi
    
    log_success "롤백 완료"
}

# 메인 배포 프로세스
main() {
    # 신호 처리 (롤백용)
    trap 'log_error "배포 중단됨"; rollback; exit 1' INT TERM
    
    check_requirements
    
    # 이미지 빌드
    build_image
    
    # 이미지 푸시 (필요한 경우)
    push_image
    
    # 환경에 따른 배포
    case "$ENVIRONMENT" in
        "kubernetes")
            deploy_kubernetes
            ;;
        "development")
            deploy_docker_compose
            ;;
        "production"|"staging")
            deploy_docker_compose
            ;;
        *)
            log_error "지원하지 않는 환경: $ENVIRONMENT"
            exit 1
            ;;
    esac
    
    # 헬스체크
    health_check
    
    # 정리
    cleanup
    
    log_success "🎉 StudyMate API 배포 완료!"
    log_info "서비스 URL: http://localhost:8000"
    log_info "헬스체크: http://localhost:8000/health/"
    log_info "API 문서: http://localhost:8000/api/docs/"
}

# 사용법 출력
usage() {
    echo "사용법: $0 [OPTIONS]"
    echo ""
    echo "옵션:"
    echo "  -e, --environment ENVIRONMENT    배포 환경 (development|staging|production|kubernetes)"
    echo "  -t, --tag TAG                    Docker 이미지 태그"
    echo "  -r, --registry REGISTRY          Docker 레지스트리"
    echo "  -h, --help                       도움말 출력"
    echo ""
    echo "예시:"
    echo "  $0 -e development                 # 개발 환경 배포"
    echo "  $0 -e production -t v1.0.0        # 프로덕션 환경 배포"
    echo "  $0 -e kubernetes -r myregistry    # Kubernetes 배포"
}

# 명령행 인수 처리
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -t|--tag)
            IMAGE_TAG="$2"
            FULL_IMAGE="${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
            shift 2
            ;;
        -r|--registry)
            REGISTRY="$2"
            FULL_IMAGE="${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            log_error "알 수 없는 옵션: $1"
            usage
            exit 1
            ;;
    esac
done

# 메인 함수 실행
main