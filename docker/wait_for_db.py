#!/usr/bin/env python
"""
데이터베이스 연결 대기 스크립트

Docker 컨테이너가 시작될 때 데이터베이스가 준비될 때까지 대기합니다.
"""

import os
import sys
import time
import django
from django.conf import settings
from django.db import connections
from django.db.utils import OperationalError

# Django 설정 로드
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'studymate_api.settings')
django.setup()

def wait_for_database():
    """데이터베이스 연결을 기다립니다."""
    print("데이터베이스 연결을 확인하는 중...")
    
    max_retries = 60  # 최대 60초 대기
    retry_interval = 1  # 1초마다 재시도
    
    for attempt in range(max_retries):
        try:
            # 기본 데이터베이스 연결 테스트
            db_conn = connections['default']
            db_conn.cursor()
            print("✅ 데이터베이스 연결 성공!")
            return True
            
        except OperationalError as e:
            print(f"⏳ 데이터베이스 연결 대기 중... ({attempt + 1}/{max_retries})")
            print(f"   오류: {e}")
            
            if attempt == max_retries - 1:
                print("❌ 데이터베이스 연결 실패: 최대 재시도 횟수 초과")
                return False
            
            time.sleep(retry_interval)
        
        except Exception as e:
            print(f"❌ 예상치 못한 오류: {e}")
            return False
    
    return False

def wait_for_redis():
    """Redis 연결을 기다립니다."""
    try:
        from django.core.cache import cache
        
        print("Redis 연결을 확인하는 중...")
        
        max_retries = 30  # 최대 30초 대기
        retry_interval = 1
        
        for attempt in range(max_retries):
            try:
                cache.set('connection_test', 'ok', 10)
                cache.get('connection_test')
                print("✅ Redis 연결 성공!")
                return True
                
            except Exception as e:
                print(f"⏳ Redis 연결 대기 중... ({attempt + 1}/{max_retries})")
                
                if attempt == max_retries - 1:
                    print("⚠️ Redis 연결 실패 (계속 진행)")
                    return False
                
                time.sleep(retry_interval)
    
    except ImportError:
        print("ℹ️ Redis가 설정되지 않음")
        return True
    
    return False

def main():
    """메인 함수"""
    print("🔄 서비스 연결 상태 확인 시작")
    
    # 데이터베이스 대기
    if not wait_for_database():
        print("❌ 데이터베이스 연결 실패로 인한 종료")
        sys.exit(1)
    
    # Redis 대기 (실패해도 계속 진행)
    wait_for_redis()
    
    print("✅ 모든 서비스 연결 확인 완료")

if __name__ == '__main__':
    main()