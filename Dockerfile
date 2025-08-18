# StudyMate API Docker 이미지
# 멀티스테이지 빌드를 사용하여 이미지 크기 최적화

# 1단계: 빌드 환경
FROM python:3.11-slim as builder

# 환경변수 설정
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY requirements.txt /tmp/requirements.txt
RUN pip install --user -r /tmp/requirements.txt

# 2단계: 실행 환경
FROM python:3.11-slim as runtime

# 환경변수 설정
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/studymate/.local/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=studymate_api.settings

# 런타임 의존성 설치
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 보안을 위한 비root 사용자 생성
RUN groupadd -r studymate && useradd -r -g studymate studymate

# 작업 디렉토리 설정
WORKDIR /app

# 빌드 단계에서 설치된 Python 패키지 복사
COPY --from=builder /root/.local /home/studymate/.local

# 애플리케이션 코드 복사
COPY --chown=studymate:studymate . .

# 정적 파일 및 미디어 디렉토리 생성
RUN mkdir -p /app/staticfiles /app/media \
    && chown -R studymate:studymate /app

# 비root 사용자로 전환
USER studymate

# 포트 노출
EXPOSE 8000

# 헬스체크 설정
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# 엔트리포인트 스크립트 실행
ENTRYPOINT ["./docker/entrypoint.sh"]

# 기본 명령어
CMD ["gunicorn", "--config", "docker/gunicorn.conf.py", "studymate_api.wsgi:application"]