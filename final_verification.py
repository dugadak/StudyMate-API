#!/usr/bin/env python
"""
StudyMate API 최종 검증 스크립트

이 스크립트는 다음을 검증합니다:
- 모든 모듈 import 가능 여부
- 데이터베이스 마이그레이션 상태
- 필수 설정 확인
- API 엔드포인트 응답 확인
- 보안 설정 검증
- 성능 기준 확인
"""

import os
import sys
import importlib
import subprocess
import requests
import json
from pathlib import Path
from typing import Dict, List, Tuple, Any
from datetime import datetime

# Django 설정 로드
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'studymate_api.settings')

class StudyMateVerifier:
    """StudyMate API 최종 검증 클래스"""
    
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent
        self.results = []
        self.base_url = "http://localhost:8000"
        
    def log_result(self, test_name: str, success: bool, message: str, details: Any = None):
        """테스트 결과 로깅"""
        result = {
            'test_name': test_name,
            'success': success,
            'message': message,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        self.results.append(result)
        
        status_icon = "✅" if success else "❌"
        print(f"{status_icon} {test_name}: {message}")
        
        if details and not success:
            print(f"   세부정보: {details}")
    
    def verify_imports(self) -> bool:
        """모든 주요 모듈 import 검증"""
        print("\n📦 모듈 Import 검증")
        
        modules_to_test = [
            'studymate_api.settings',
            'studymate_api.urls',
            'studymate_api.cache',
            'studymate_api.exceptions',
            'studymate_api.middleware',
            'studymate_api.security',
            'studymate_api.validators',
            'studymate_api.types',
            'studymate_api.health',
            'studymate_api.monitoring_middleware',
            'accounts.models',
            'accounts.views',
            'accounts.serializers',
            'study.models',
            'study.services',
            'quiz.models',
            'subscription.models',
            'notifications.models'
        ]
        
        all_success = True
        
        for module_name in modules_to_test:
            try:
                importlib.import_module(module_name)
                self.log_result(f"Import {module_name}", True, "성공")
            except ImportError as e:
                self.log_result(f"Import {module_name}", False, "실패", str(e))
                all_success = False
            except Exception as e:
                self.log_result(f"Import {module_name}", False, "예외 발생", str(e))
                all_success = False
        
        return all_success
    
    def verify_django_setup(self) -> bool:
        """Django 설정 검증"""
        print("\n⚙️ Django 설정 검증")
        
        try:
            import django
            from django.conf import settings
            from django.core.management import execute_from_command_line
            
            django.setup()
            
            # Django 버전 확인
            self.log_result("Django 버전", True, f"Django {django.get_version()}")
            
            # 필수 설정 확인
            required_settings = [
                'SECRET_KEY', 'DATABASES', 'INSTALLED_APPS', 
                'MIDDLEWARE', 'ROOT_URLCONF'
            ]
            
            for setting_name in required_settings:
                if hasattr(settings, setting_name):
                    value = getattr(settings, setting_name)
                    if value:
                        self.log_result(f"설정 {setting_name}", True, "존재")
                    else:
                        self.log_result(f"설정 {setting_name}", False, "비어있음")
                        return False
                else:
                    self.log_result(f"설정 {setting_name}", False, "없음")
                    return False
            
            return True
            
        except Exception as e:
            self.log_result("Django 설정", False, "실패", str(e))
            return False
    
    def verify_database(self) -> bool:
        """데이터베이스 연결 및 마이그레이션 확인"""
        print("\n🗄️ 데이터베이스 검증")
        
        try:
            import django
            django.setup()
            
            from django.db import connection
            from django.core.management.commands.migrate import Command as MigrateCommand
            
            # 데이터베이스 연결 테스트
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                if result and result[0] == 1:
                    self.log_result("데이터베이스 연결", True, "성공")
                else:
                    self.log_result("데이터베이스 연결", False, "연결 실패")
                    return False
            
            # 마이그레이션 상태 확인
            try:
                result = subprocess.run(
                    [sys.executable, 'manage.py', 'showmigrations', '--plan'],
                    capture_output=True, text=True, cwd=self.base_dir
                )
                
                if result.returncode == 0:
                    output = result.stdout
                    if '[X]' in output:  # 적용된 마이그레이션이 있음
                        self.log_result("마이그레이션 상태", True, "마이그레이션 적용됨")
                    else:
                        self.log_result("마이그레이션 상태", False, "마이그레이션 미적용")
                        return False
                else:
                    self.log_result("마이그레이션 확인", False, "명령 실행 실패", result.stderr)
                    return False
                    
            except Exception as e:
                self.log_result("마이그레이션 확인", False, "오류", str(e))
                return False
            
            return True
            
        except Exception as e:
            self.log_result("데이터베이스 검증", False, "실패", str(e))
            return False
    
    def verify_cache(self) -> bool:
        """캐시 시스템 확인"""
        print("\n🚀 캐시 시스템 검증")
        
        try:
            import django
            django.setup()
            
            from django.core.cache import cache
            
            # 캐시 읽기/쓰기 테스트
            test_key = 'verification_test'
            test_value = 'test_value_123'
            
            cache.set(test_key, test_value, 60)
            cached_value = cache.get(test_key)
            
            if cached_value == test_value:
                self.log_result("캐시 읽기/쓰기", True, "성공")
                cache.delete(test_key)  # 정리
                return True
            else:
                self.log_result("캐시 읽기/쓰기", False, "실패")
                return False
                
        except Exception as e:
            self.log_result("캐시 검증", False, "실패", str(e))
            return False
    
    def verify_api_endpoints(self) -> bool:
        """주요 API 엔드포인트 확인"""
        print("\n🌐 API 엔드포인트 검증")
        
        endpoints_to_test = [
            ('/health/', 'GET', 200),
            ('/health/ready/', 'GET', 200),
            ('/health/alive/', 'GET', 200),
            ('/metrics/', 'GET', 200),
            ('/api/docs/', 'GET', 200),
            ('/api/schema/', 'GET', 200),
        ]
        
        all_success = True
        
        for endpoint, method, expected_status in endpoints_to_test:
            try:
                if method == 'GET':
                    response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
                else:
                    response = requests.post(f"{self.base_url}{endpoint}", timeout=10)
                
                if response.status_code == expected_status:
                    self.log_result(f"API {endpoint}", True, f"응답 코드 {response.status_code}")
                else:
                    self.log_result(f"API {endpoint}", False, 
                                  f"예상 {expected_status}, 실제 {response.status_code}")
                    all_success = False
                    
            except requests.exceptions.RequestException as e:
                self.log_result(f"API {endpoint}", False, "연결 실패", str(e))
                all_success = False
            except Exception as e:
                self.log_result(f"API {endpoint}", False, "오류", str(e))
                all_success = False
        
        return all_success
    
    def verify_security_settings(self) -> bool:
        """보안 설정 확인"""
        print("\n🔒 보안 설정 검증")
        
        try:
            import django
            django.setup()
            
            from django.conf import settings
            
            security_checks = []
            
            # DEBUG 설정 확인 (프로덕션에서는 False여야 함)
            if hasattr(settings, 'DEBUG'):
                if not settings.DEBUG:
                    security_checks.append(("DEBUG 설정", True, "False (안전)"))
                else:
                    security_checks.append(("DEBUG 설정", False, "True (위험)"))
            else:
                security_checks.append(("DEBUG 설정", False, "설정 없음"))
            
            # SECRET_KEY 설정 확인
            if hasattr(settings, 'SECRET_KEY') and settings.SECRET_KEY:
                if len(settings.SECRET_KEY) >= 50:
                    security_checks.append(("SECRET_KEY 길이", True, "충분함"))
                else:
                    security_checks.append(("SECRET_KEY 길이", False, "너무 짧음"))
            else:
                security_checks.append(("SECRET_KEY", False, "설정 없음"))
            
            # ALLOWED_HOSTS 확인
            if hasattr(settings, 'ALLOWED_HOSTS') and settings.ALLOWED_HOSTS:
                if '*' not in settings.ALLOWED_HOSTS:
                    security_checks.append(("ALLOWED_HOSTS", True, "안전하게 설정됨"))
                else:
                    security_checks.append(("ALLOWED_HOSTS", False, "와일드카드 사용 (위험)"))
            else:
                security_checks.append(("ALLOWED_HOSTS", False, "설정 없음"))
            
            # 보안 미들웨어 확인
            required_middleware = [
                'django.middleware.security.SecurityMiddleware',
                'studymate_api.middleware.SecurityMiddleware',
                'studymate_api.middleware.RateLimitMiddleware'
            ]
            
            middleware = getattr(settings, 'MIDDLEWARE', [])
            for mw in required_middleware:
                if mw in middleware:
                    security_checks.append((f"미들웨어 {mw.split('.')[-1]}", True, "활성화됨"))
                else:
                    security_checks.append((f"미들웨어 {mw.split('.')[-1]}", False, "누락됨"))
            
            # 결과 로깅
            all_success = True
            for check_name, success, message in security_checks:
                self.log_result(check_name, success, message)
                if not success:
                    all_success = False
            
            return all_success
            
        except Exception as e:
            self.log_result("보안 설정 검증", False, "실패", str(e))
            return False
    
    def verify_file_structure(self) -> bool:
        """필수 파일 구조 확인"""
        print("\n📁 파일 구조 검증")
        
        required_files = [
            'manage.py',
            'requirements.txt',
            'Dockerfile',
            'docker-compose.yml',
            '.env.example',
            'studymate_api/settings.py',
            'studymate_api/urls.py',
            'studymate_api/wsgi.py',
            'studymate_api/types.py',
            'studymate_api/security.py',
            'studymate_api/health.py',
            'pytest.ini',
            'mypy.ini',
            '.flake8',
            'pyproject.toml'
        ]
        
        required_directories = [
            'accounts',
            'study', 
            'quiz',
            'subscription',
            'notifications',
            'tests',
            'docker',
            'k8s',
            'scripts'
        ]
        
        all_success = True
        
        # 필수 파일 확인
        for file_path in required_files:
            full_path = self.base_dir / file_path
            if full_path.exists():
                self.log_result(f"파일 {file_path}", True, "존재")
            else:
                self.log_result(f"파일 {file_path}", False, "없음")
                all_success = False
        
        # 필수 디렉토리 확인
        for dir_path in required_directories:
            full_path = self.base_dir / dir_path
            if full_path.exists() and full_path.is_dir():
                self.log_result(f"디렉토리 {dir_path}", True, "존재")
            else:
                self.log_result(f"디렉토리 {dir_path}", False, "없음")
                all_success = False
        
        return all_success
    
    def verify_dependencies(self) -> bool:
        """의존성 패키지 확인"""
        print("\n📦 의존성 검증")
        
        critical_packages = [
            'django',
            'djangorestframework',
            'celery',
            'redis',
            'psycopg2',
            'gunicorn',
            'pytest',
            'mypy'
        ]
        
        all_success = True
        
        for package in critical_packages:
            try:
                result = subprocess.run(
                    [sys.executable, '-c', f'import {package}'],
                    capture_output=True, text=True
                )
                
                if result.returncode == 0:
                    self.log_result(f"패키지 {package}", True, "설치됨")
                else:
                    self.log_result(f"패키지 {package}", False, "설치 안됨")
                    all_success = False
                    
            except Exception as e:
                self.log_result(f"패키지 {package}", False, "확인 실패", str(e))
                all_success = False
        
        return all_success
    
    def generate_final_report(self) -> Dict[str, Any]:
        """최종 검증 리포트 생성"""
        print("\n📋 최종 검증 리포트 생성")
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r['success'])
        failed_tests = total_tests - passed_tests
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        report = {
            'verification_summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': failed_tests,
                'success_rate': success_rate,
                'timestamp': datetime.now().isoformat()
            },
            'test_results': self.results,
            'recommendations': []
        }
        
        # 실패한 테스트에 대한 권장사항 생성
        failed_results = [r for r in self.results if not r['success']]
        
        for failed_result in failed_results:
            if 'import' in failed_result['test_name'].lower():
                report['recommendations'].append(
                    f"모듈 {failed_result['test_name']} 오류 수정 필요"
                )
            elif 'database' in failed_result['test_name'].lower():
                report['recommendations'].append(
                    "데이터베이스 연결 설정 및 마이그레이션 확인 필요"
                )
            elif 'api' in failed_result['test_name'].lower():
                report['recommendations'].append(
                    "API 서버 실행 상태 확인 필요"
                )
            elif 'security' in failed_result['test_name'].lower():
                report['recommendations'].append(
                    "보안 설정 강화 필요"
                )
        
        # 리포트 저장
        report_file = self.base_dir / 'verification_report.json'
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"   📄 리포트 저장됨: {report_file}")
        
        # 요약 출력
        print(f"\n🎯 최종 검증 결과:")
        print(f"   총 테스트: {total_tests}")
        print(f"   통과: {passed_tests}")
        print(f"   실패: {failed_tests}")
        print(f"   성공률: {success_rate:.2f}%")
        
        if success_rate >= 90:
            print(f"   🎉 검증 완료! StudyMate API가 배포 준비되었습니다.")
        elif success_rate >= 70:
            print(f"   ⚠️ 일부 개선이 필요하지만 기본 기능은 작동합니다.")
        else:
            print(f"   ❌ 심각한 문제가 있습니다. 배포 전 수정이 필요합니다.")
        
        return report
    
    def run_all_verifications(self) -> bool:
        """모든 검증 실행"""
        print("🔍 StudyMate API 최종 검증 시작")
        print("=" * 60)
        
        verification_steps = [
            ("파일 구조", self.verify_file_structure),
            ("의존성", self.verify_dependencies),
            ("모듈 Import", self.verify_imports),
            ("Django 설정", self.verify_django_setup),
            ("데이터베이스", self.verify_database),
            ("캐시", self.verify_cache),
            ("보안 설정", self.verify_security_settings),
            ("API 엔드포인트", self.verify_api_endpoints),
        ]
        
        overall_success = True
        
        for step_name, step_function in verification_steps:
            try:
                success = step_function()
                if not success:
                    overall_success = False
            except Exception as e:
                self.log_result(f"{step_name} 검증", False, "예외 발생", str(e))
                overall_success = False
        
        # 최종 리포트 생성
        self.generate_final_report()
        
        print("\n" + "=" * 60)
        if overall_success:
            print("🎉 모든 검증이 완료되었습니다!")
        else:
            print("⚠️ 일부 검증에서 문제가 발견되었습니다.")
        
        return overall_success

def main():
    """메인 함수"""
    verifier = StudyMateVerifier()
    success = verifier.run_all_verifications()
    
    # 종료 코드 설정
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()