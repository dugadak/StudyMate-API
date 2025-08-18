#!/bin/bash
set -e

# StudyMate API Docker 엔트리포인트 스크립트

echo "🚀 StudyMate API 시작 중..."

# 환경변수 기본값 설정
export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-studymate_api.settings}
export DEBUG=${DEBUG:-False}
export ENVIRONMENT=${ENVIRONMENT:-production}

# 데이터베이스 연결 대기
echo "📡 데이터베이스 연결 대기 중..."
python docker/wait_for_db.py

# 데이터베이스 마이그레이션
echo "🗄️ 데이터베이스 마이그레이션 실행 중..."
python manage.py migrate --noinput

# 정적 파일 수집
if [ "$COLLECT_STATIC" = "true" ]; then
    echo "📦 정적 파일 수집 중..."
    python manage.py collectstatic --noinput --clear
fi

# 슈퍼유저 생성 (개발 환경에서만)
if [ "$CREATE_SUPERUSER" = "true" ] && [ "$ENVIRONMENT" != "production" ]; then
    echo "👑 슈퍼유저 생성 중..."
    python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', 'admin@studymate.com', 'admin123!')
    print('슈퍼유저가 생성되었습니다.')
else:
    print('슈퍼유저가 이미 존재합니다.')
"
fi

# 캐시 워밍업
echo "🔥 캐시 워밍업 중..."
python manage.py shell -c "
from django.core.cache import cache
cache.set('health_check', 'ok', 3600)
print('캐시 워밍업 완료')
"

# Django 시스템 체크
echo "🔍 Django 시스템 체크 실행 중..."
python manage.py check --deploy

# 애플리케이션 시작 시간 기록
python -c "
import time
import os
start_time = str(time.time())
with open('/tmp/app_start_time', 'w') as f:
    f.write(start_time)
print(f'애플리케이션 시작 시간: {start_time}')
"

echo "✅ 초기화 완료! 애플리케이션을 시작합니다..."

# 전달된 명령 실행
exec "$@"